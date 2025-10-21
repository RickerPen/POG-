import pandas as pd
from typing import Dict, Optional, List, Tuple

class RemoveTray:
    """
    一个用于处理POG（Planogram）相关数据的类。
    其职责是读取、清理数据（如移除tray），并对数据进行空间分析。
    """
    def __init__(self):
        self.dataframes: Dict[str, pd.DataFrame] = {}
        self.affected_layers_by_removal: List[Tuple[int, int]] = []
        print("RemoveTray 对象已创建。")

    def load_data(self, file_path: str, key_name: str):
        print(f"--- 开始加载: {file_path} ---")
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path)
            elif file_path.endswith('.xlsx'):
                df = pd.read_excel(file_path)
            else:
                print(f"[警告] 不支持的文件格式: {file_path}。")
                return
            self.dataframes[key_name] = df
            print(f"文件加载成功，共 {len(df)} 行。数据已存储为 '{key_name}'。")
        except FileNotFoundError:
            print(f"[错误] 文件未找到，请检查路径: {file_path}")
        except Exception as e:
            print(f"[错误] 加载文件 {file_path} 时发生未知错误: {e}")
            
    def remove_tray_items(self, data_key: str):
        print(f"\n--- 开始执行 'remove_tray_items' 操作 (目标: '{data_key}') ---")
        if data_key not in self.dataframes:
            print(f"[错误] 未找到要处理的数据: '{data_key}'。")
            return
        df = self.dataframes[data_key]
        if 'item_type' not in df.columns:
            print(f"[错误] 在数据 '{data_key}' 中未找到 'item_type' 列。")
            return
        trays_df = df[df['item_type'] == 'tray']
        if not trays_df.empty:
            affected_layers = trays_df[['module_id', 'layer_id']].drop_duplicates()

            new_layers = [tuple(row) for row in affected_layers.to_numpy()]
            for layer in new_layers:
                if layer not in self.affected_layers_by_removal:
                    self.affected_layers_by_removal.append(layer)
            
            print(f"识别到 {len(self.affected_layers_by_removal)} 个因移除 'tray' 而受影响的货架层。")
        else:
            print("未发现 item_type 为 'tray' 的行，无需删除。")
            
        initial_row_count = len(df)
        filtered_df = df[df['item_type'] != 'tray'].copy()
        rows_removed = initial_row_count - len(filtered_df)
        print(f"已删除 {rows_removed} 个 item_type 为 'tray' 的行。")
        self.dataframes[data_key] = filtered_df

    def analyze_layer_space(self, data_key: str, total_layer_width: int = 1000) -> Optional[pd.DataFrame]:
        print(f"\n--- 开始分析 '{data_key}' 的货架层空间 ---")
        if data_key not in self.dataframes:
            print(f"[错误] 未找到要分析的数据: '{data_key}'。")
            return None
        pog_df = self.dataframes[data_key]
        required_cols = ['module_id', 'layer_id', 'item_width']
        if not all(col in pog_df.columns for col in required_cols):
            print(f"[错误] 数据 '{data_key}' 缺少必要的列。需要: {required_cols}")
            return None
        if pog_df.empty:
            return pd.DataFrame(columns=['module_id', 'layer_id', 'item_count', 'used_width', 'total_width', 'remaining_width'])
        layer_summary = pog_df.groupby(['module_id', 'layer_id']).agg(used_width=('item_width', 'sum'), item_count=('item_code', 'count')).reset_index()
        layer_summary['total_width'] = total_layer_width
        layer_summary['remaining_width'] = layer_summary['total_width'] - layer_summary['used_width']
        return layer_summary[['module_id', 'layer_id', 'item_count', 'used_width', 'total_width', 'remaining_width']]

    def save_processed_data(self, data_key: str, output_filename: str):
        """
        将 self.dataframes 中指定的数据保存到新的 Excel 文件中。
        """
        print(f"\n--- 准备保存数据: '{data_key}' ---")
        
        if data_key not in self.dataframes:
            print(f"[错误] 未找到要保存的数据: '{data_key}'。")
            return
            
        df_to_save = self.dataframes[data_key]

        if df_to_save.empty:
            print(f"[警告] 数据 '{data_key}' 为空，将创建一个空的Excel文件。")

        try:
            df_to_save.to_csv(output_filename, index=False)
            print(f"数据已成功保存到: {output_filename}")
        except Exception as e:
            print(f"[错误] 保存文件时发生错误: {e}")

class FillLayer(RemoveTray):
    """
    负责商品填充逻辑的类。
    继承自 RemoveTray，以利用其数据加载和预处理能力。
    """
    def __init__(self):
        # 首先，调用父类的构造函数来初始化 self.dataframes 和 self.affected_layers_by_removal
        super().__init__()
        # 初始化本类特有的属性
        self.affected_layer_space: Optional[pd.DataFrame] = None
        self.sorted_items_by_layer: Dict[Tuple[int, int], pd.DataFrame] = {}
        self.sorted_items_by_position: Dict[Tuple[int, int], pd.DataFrame] = {}
        print("FillLayer 对象已创建，准备执行填充逻辑。")

    def calculate_space_for_affected_layers(self, pog_data_key: str = 'pog_result'):
        print("\n--- 开始计算受影响货架层的剩余空间 ---")
        if not self.affected_layers_by_removal:
            print("[信息] 没有受影响的货架层，无需计算。")
            return
        
        all_layers_space = self.analyze_layer_space(data_key=pog_data_key)
        
        if all_layers_space is None or all_layers_space.empty:
            print("[警告] 空间分析未产生有效结果，无法计算受影响层空间。")
            # 即使分析结果为空，也创建一个空的DataFrame以避免后续错误
            self.affected_layer_space = pd.DataFrame(columns=['module_id', 'layer_id', 'item_count', 'used_width', 'total_width', 'remaining_width'])
            return

        all_layers_space_indexed = all_layers_space.set_index(['module_id', 'layer_id'])
        affected_space = all_layers_space_indexed.reindex(self.affected_layers_by_removal)
        
        self.affected_layer_space = affected_space.reset_index()
        print("已成功计算并存储受影响货架层的空间信息。")

    def sort_items_by_sales_in_affected_layers(self, pog_data_key: str = 'pog_result', sales_file_path: str = '开发所需测试数据\开发所需测试数据\sales_item_sum.csv'):
        """
        在每个受影响的层中，根据销量对剩余商品进行降序排序。
        """
        print(f"\n--- 开始根据销量排序 '{pog_data_key}' 中受影响层的商品 ---")
        if pog_data_key not in self.dataframes or self.affected_layers_by_removal is None:
            print("[错误] POG数据或受影响层列表为空，无法排序。")
            return

        # 1. 加载销量数据
        try:
            sales_df = pd.read_csv(sales_file_path)
            required_sales_cols = ['item_code', 'sales']
            if not all(col in sales_df.columns for col in required_sales_cols):
                print(f"[错误] 销量文件 '{sales_file_path}' 缺少必要列，需要: {required_sales_cols}")
                return
        except FileNotFoundError:
            print(f"[错误] 销量文件未找到: {sales_file_path}")
            return
        except Exception as e:
            print(f"[错误] 读取销量文件时出错: {e}")
            return

        # 2. 遍历每个受影响的层
        pog_df = self.dataframes[pog_data_key]
        if 'item_code' not in pog_df.columns:
            print(f"[错误] POG数据中缺少 'item_code' 列，无法与销量数据匹配。")
            return
            
        for module_id, layer_id in self.affected_layers_by_removal:
            # 筛选出当前层的商品
            layer_items_df = pog_df[(pog_df['module_id'] == module_id) & (pog_df['layer_id'] == layer_id)].copy()
            
            # 与销量数据合并
            merged_df = pd.merge(layer_items_df, sales_df, on='item_code', how='left')
            # 用0填充没有销量的商品
            merged_df['sales'] = merged_df['sales'].fillna(0)
            
            # 按销量降序排序
            sorted_df = merged_df.sort_values(by='sales', ascending=False)
            
            # 存储结果
            self.sorted_items_by_layer[(module_id, layer_id)] = sorted_df
            print(f"已完成对 Module {module_id}, Layer {layer_id} 中商品的排序。")

    def sort_items_by_position_in_affected_layers(self, pog_data_key: str = 'pog_result'):
        """
        在每个受影响的层中，根据物理位置（position）对商品进行升序排序。
        """
        print(f"\n--- 开始根据物理位置排序 '{pog_data_key}' 中受影响层的商品 ---")
        if pog_data_key not in self.dataframes or not self.affected_layers_by_removal:
            print("[错误] POG数据或受影响层列表为空，无法排序。")
            return

        pog_df = self.dataframes[pog_data_key]
        
        # 1. 验证 'position' 列是否存在
        if 'position' not in pog_df.columns:
            print(f"[错误] POG数据中缺少 'position' 列，无法按位置排序。")
            return

        # 2. 遍历每个受影响的层
        for module_id, layer_id in self.affected_layers_by_removal:
            # 筛选出当前层的商品
            layer_items_df = pog_df[(pog_df['module_id'] == module_id) & (pog_df['layer_id'] == layer_id)].copy()
            
            # 如果该层在移除tray后已无商品，则跳过
            if layer_items_df.empty:
                print(f"Module {module_id}, Layer {layer_id} 中没有商品，无需排序。")
                continue

            # 按 'position' 列从小到大排序
            sorted_df = layer_items_df.sort_values(by='position', ascending=True)
            
            # 存储结果
            self.sorted_items_by_position[(module_id, layer_id)] = sorted_df
            print(f"已完成对 Module {module_id}, Layer {layer_id} 中商品的位置排序。")
            
    def fill_and_reposition_layers(self, pog_data_key: str = 'pog_result', total_layer_width: int = 1000):
        """
        使用本层销量最高的商品填充剩余空间（每个商品总数最多2个），
        确保复制品与原商品邻近，然后重新计算所有商品的位置。
        """
        print("\n" + "="*50)
        print("      开始执行核心填充与重新定位功能 (最多2个/项)")
        print("="*50)

        updated_layers_data = []

        # 1. 遍历每个受影响的层
        for layer_tuple in self.affected_layers_by_removal:
            module_id, layer_id = layer_tuple
            print(f"\n--- 正在处理 Layer: {layer_tuple} ---")

            # 2. 条件检查
            if (layer_tuple not in self.sorted_items_by_position or 
                self.sorted_items_by_position[layer_tuple].empty):
                print(f"Layer {layer_tuple} 中无剩余商品，跳过填充操作。")
                continue
            if (layer_tuple not in self.sorted_items_by_layer or 
                self.sorted_items_by_layer[layer_tuple].empty):
                print(f"Layer {layer_tuple} 中没有可用于填充的候选商品，跳过。")
                continue

            # 3. 获取数据源
            fill_candidates = self.sorted_items_by_layer[layer_tuple]
            original_items_by_pos = self.sorted_items_by_position[layer_tuple].copy()
            
            space_query = self.affected_layer_space.query(f"module_id == {module_id} and layer_id == {layer_id}")
            initial_remaining_width = space_query['remaining_width'].iloc[0]
            current_remaining_width = initial_remaining_width

            # 4. 步骤 1: 虚拟填充，计算每个商品需要复制多少
            copies_to_add = {}
            
            # --- 新逻辑: 统计原始数量 ---
            # .to_dict() 确保我们得到一个可修改的字典
            current_item_counts = original_items_by_pos['item_code'].value_counts().to_dict()
            print(f"  原始商品数量: {current_item_counts}")
            
            print("  开始虚拟填充 (最多2个/项)...")
            for _, candidate in fill_candidates.iterrows():
                item_code = candidate['item_code']
                item_width = candidate['item_width']
                
                # 获取当前该商品的总数（原始+已添加的复制品）
                current_count = current_item_counts.get(item_code, 0)
                
                # --- MODIFIED: 循环条件中增加 'current_count < 2' ---
                while current_count < 2 and current_remaining_width >= item_width:
                    # 规则检查通过，可以添加一个
                    copies_to_add[item_code] = copies_to_add.get(item_code, 0) + 1
                    current_remaining_width -= item_width
                    
                    # 关键：更新运行总数
                    current_count += 1
                    current_item_counts[item_code] = current_count
                    
                    print(f"    + 虚拟添加 {item_code} (宽度: {item_width})。总数: {current_count}。剩余空间: {current_remaining_width:.2f}")

            # 5. 步骤 2: 构建邻近布局 (此部分逻辑无需修改)
            final_item_list_for_layer = []
            if not copies_to_add:
                print("  剩余空间不足以填充任何新商品。")
                all_items_on_layer_df = original_items_by_pos
            else:
                print("  虚拟填充完成。开始构建邻近布局...")
                for _, original_item in original_items_by_pos.iterrows():
                    final_item_list_for_layer.append(original_item.to_dict())
                    item_code = original_item['item_code']
                    num_copies = copies_to_add.get(item_code, 0)
                    if num_copies > 0:
                        print(f"    > 为 {item_code} 添加 {num_copies} 个邻近复制品。")
                        copy_item_dict = original_item.to_dict()
                        copy_item_dict['position'] = -1
                        for _ in range(num_copies):
                            final_item_list_for_layer.append(copy_item_dict.copy())
                        del copies_to_add[item_code]
                all_items_on_layer_df = pd.DataFrame(final_item_list_for_layer)
            
            # 6. 步骤 3: 重新定位 (此部分逻辑无需修改)
            total_items_width = all_items_on_layer_df['item_width'].sum()
            final_remaining_width = total_layer_width - total_items_width
            num_items = len(all_items_on_layer_df)
            spacing = (final_remaining_width / (num_items - 1)) if num_items > 1 else 0
            print(f"  该层商品总数: {num_items}, 总宽度: {total_items_width:.2f}, 最终间距: {spacing:.2f}")
            new_positions = []
            current_pos = 0.0
            for _, item in all_items_on_layer_df.iterrows():
                new_positions.append(current_pos)
                current_pos += item['item_width'] + spacing
            all_items_on_layer_df['position'] = new_positions
            updated_layers_data.append(all_items_on_layer_df)

        # 7. 最终更新 (此部分逻辑无需修改)
        if not updated_layers_data:
            print("\n没有层被更新，最终结果与移除tray后相同。")
            self.dataframes['pog_result_filled'] = self.dataframes[pog_data_key]
            return
        final_updated_df = pd.concat(updated_layers_data, ignore_index=True)
        original_pog_df = self.dataframes[pog_data_key]
        affected_layers_index = pd.MultiIndex.from_tuples(self.affected_layers_by_removal, names=['module_id', 'layer_id'])
        unaffected_df = original_pog_df.set_index(['module_id', 'layer_id']).drop(index=affected_layers_index, errors='ignore').reset_index()
        final_pog_result = pd.concat([unaffected_df, final_updated_df], ignore_index=True)
        self.dataframes['pog_result_filled'] = final_pog_result
        print("\n" + "="*50)
        print("      核心填充与重新定位功能执行完毕！")
        print("      最终结果已保存在 dataframes['pog_result_filled'] 中")
        print("="*50)

    def save_final_result(self, output_file_path: str, data_key: str = 'pog_result_filled'):
        """
        将最终处理完成的POG数据保存到CSV文件中。

        参数:
            output_file_path (str): 输出的CSV文件名 (例如 'final_pog.csv')。
            data_key (str): 要保存的数据在 self.dataframes 字典中的键名。
        """
        print(f"\n--- 准备保存最终结果: '{data_key}' ---")
        
        if data_key not in self.dataframes:
            print(f"[错误] 未找到要保存的最终数据: '{data_key}'。请先执行填充流程。")
            return
            
        df_to_save = self.dataframes[data_key]

        # 为了确保输出文件的整洁，我们可以按层和位置进行最后一次排序
        df_to_save_sorted = df_to_save.sort_values(by=['module_id', 'layer_id', 'position']).reset_index(drop=True)

        try:
            # index=False 避免将DataFrame的索引写入CSV文件
            df_to_save_sorted.to_csv(output_file_path, index=False, encoding='utf-8-sig')
            print(f"最终结果已成功保存到: {output_file_path}")
        except Exception as e:
            print(f"[错误] 保存文件时发生错误: {e}")


filler = FillLayer()
filler.load_data(file_path="开发所需测试数据\开发所需测试数据\pog_result.csv", key_name='pog_result')
analyse_result = filler.analyze_layer_space(data_key='pog_result')
# print("\n--- 分析结果预览 ---")
# print(analyse_result)
filler.remove_tray_items(data_key='pog_result')
filler.calculate_space_for_affected_layers()

# 调用方法一：按销量排序
filler.sort_items_by_sales_in_affected_layers()

# 调用方法二：按位置排序
filler.sort_items_by_position_in_affected_layers()
filler.fill_and_reposition_layers()

# --- 新增步骤: 调用保存方法 ---
filler.save_final_result(output_file_path="pog_result_final_output.csv")
