---

# **POG 去出托盘处理程序使用文档**

本文档旨在说明 POG\_remove\_tray Python 程序的用法。该程序通过面向对象的方式，封装了对货架图（Planogram）数据的读取、清理、空间分析、智能填充和重新布局等一系列功能。

## **核心组件**

程序主要由两个类构成：RemoveTray 和 FillLayer。

### **1\. RemoveTray 类**

这是项目的基础类，主要负责数据的加载和初步清理。

**方法简介:**

* \_\_init\_\_(): 构造函数，初始化数据容器。  
* load\_data(file\_path, key\_name): 从指定的 CSV 或 Excel 文件加载数据到内存中。  
* remove\_tray\_items(data\_key): **核心清理方法**。移除 item\_type 为 'tray' 的所有行，并自动记录哪些货架层因此受到了影响。  
* analyze\_layer\_space(data\_key): 分析指定数据集的货架空间使用情况，返回每个层的已用宽度、剩余宽度等信息。

### **2\. FillLayer 类**

该类继承自 RemoveTray，并在其基础上实现了更高级的商品填充和布局逻辑。

**方法简介:**

* \_\_init\_\_(): 构造函数，在初始化父类的同时，也为填充逻辑准备了专用的数据容器。  
* calculate\_space\_for\_affected\_layers(): 专门计算因移除 'tray' 而受影响的那些货架层的剩余空间。  
* sort\_items\_by\_sales\_in\_affected\_layers(): 对受影响层上的剩余商品，根据关联的销量数据进行降序排序。  
* sort\_items\_by\_position\_in\_affected\_layers(): 对受影响层上的剩余商品，根据其物理位置 (position) 进行升序排序。  
* fill\_and\_reposition\_layers(): **核心填充与布局方法**。它使用本层最高销量的商品去填充因移除 'tray' 而产生的空白空间，然后重新计算该层所有商品的位置，使它们均匀分布。  
* save\_final\_result(output\_file\_path): 将最终处理完成的货架图数据保存到指定的 CSV 文件中。

## **使用场景**

### **场景一：仅移除 Tray (不进行填充)**

**目标**：快速清理原始的 pog\_result.csv 文件，仅移除所有 item\_type 为 'tray' 的行，然后将干净的数据保存为新文件。

**实现代码**:

Python

\# 引入 FillLayer 类 (它已包含 RemoveTray 的所有功能)  
\# from your\_script\_file import FillLayer

\# 1\. 实例化对象  
processor \= FillLayer()

\# 2\. 加载原始数据  
processor.load\_data(file\_path="pog\_result.csv", key\_name='pog\_result')

\# 3\. 执行移除 tray 的操作  
processor.remove\_tray\_items(data\_key='pog\_result')

\# 4\. 保存清理后的结果  
\#    注意：此时最终结果存储在 'pog\_result' 中，而不是 'pog\_result\_filled'  
processor.save\_final\_result(  
    output\_file\_path="pog\_result\_no\_tray\_only.csv",  
    data\_key='pog\_result'   
)

print("\\n任务完成：仅移除了 tray 并已保存结果。")

### **场景二：移除 Tray 并智能填充空间**

**目标**：执行完整的自动化流程。首先移除所有 'tray'，然后用该层最高销量的商品智能填充产生的空白空间，最后重新计算所有商品的位置，使之均匀分布，并保存最终的货架图布局。

**实现代码**:

Python

\# 引入 FillLayer 类  
\# from your\_script\_file import FillLayer

\# 1\. 实例化对象  
filler \= FillLayer()

\# \--- 步骤 2: 加载与清理 \---  
filler.load\_data(file\_path="pog\_result.csv", key\_name='pog\_result')  
filler.remove\_tray\_items(data\_key='pog\_result')

\# \--- 步骤 3: 分析与准备 \---  
\# 计算受影响层的空间  
filler.calculate\_space\_for\_affected\_layers()  
\# 根据销量排序 (为填充做准备)  
filler.sort\_items\_by\_sales\_in\_affected\_layers(sales\_file\_path="sales\_item\_sum.csv")  
\# 根据位置排序 (为获取原始商品布局做准备)  
filler.sort\_items\_by\_position\_in\_affected\_layers()

\# \--- 步骤 4: 执行核心填充与布局 \---  
filler.fill\_and\_reposition\_layers()

\# \--- 步骤 5: 保存最终结果 \---  
\#    默认会保存 'pog\_result\_filled' 中的数据  
filler.save\_final\_result(output\_file\_path="pog\_result\_final\_output.csv")

print("\\n任务完成：已移除 tray、填充空间并重新布局，结果已保存。")  
