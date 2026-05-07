# DataOS 本体系统概览 - 语音导览脚本

**目标时长**: 7 分钟 (~2300 字)
**语言**: 中文
**声音角色**: march7

---

## Section 1: 开场 (sec-hero) ~30s

大家好，欢迎来到 DataOS 灵枢本体系统概览！今天我将带你全面了解 Ontology 的设计哲学、六种实体类型、七种边关系、版本管理、建模方法论，最后通过一个机场案例完整演示建模过程。整个系统的骨架就是三个数字：6 种实体类型、7 种边类型、7 阶段建模流程。我们开始吧！

## Section 2: 设计哲学 (sec-philosophy) ~40s

Ontology 架构有三大核心原则。第一，定义与实例分离：Ontology 定义数据的形状，实例承载实际内容，两者独立版本化。第二，逻辑与物理分离：业务概念存在于逻辑模型中，物理存储通过 AssetMapping 独立配置，互不干扰。第三，图模型思维：所有实体都是节点，关联都是边，天然支持级联更新和影响分析。

## Section 3: 六大实体类型 (sec-entities) ~80s

接下来看六种实体类型。

SharedPropertyType，前缀 ri.shprop，是全局可复用的属性模板。比如 iata_code 在机场、航司、航班中都需要，就定义为一个共享属性，保证各处定义一致。

PropertyType，前缀 ri.prop，是挂在具体对象上的属性，可以继承 SharedPropertyType。

InterfaceType，前缀 ri.iface，定义接口契约，规定实现者必须包含哪些属性。比如 schedulable 接口要求必须有 scheduled_time 和 actual_time。

ObjectType，前缀 ri.obj，定义业务对象，包含属性集合、实现接口、主键，映射到物理存储。

LinkType，前缀 ri.link，定义对象间的关系，有源端目标端，支持一对一、一对多、多对多，还能携带自身属性。

ActionType，前缀 ri.action，定义可执行操作，指定参数、执行引擎、安全级别和副作用。

## Section 4: 七种边类型 (sec-edges) ~50s

六种实体通过七种边连成完整图谱。BASED_ON，PropertyType 继承 SharedPropertyType 的模板。BELONGS_TO，属性从属于对象或关系。REQUIRES，接口要求实现者必须包含某个共享属性。IMPLEMENTS，对象或关系满足接口契约。EXTENDS，接口之间的继承。CONNECTS，LinkType 定义关系的源端和目标端。OPERATES_ON，动作指向它操作的实体。页面上的关系图完整展示了这七种边如何将六种实体编织在一起。

## Section 5: 版本生命周期 (sec-lifecycle) ~30s

每次 Ontology 变更都要经过四阶段流水线。Draft 阶段自由编辑，Staging 阶段校验审查，Snapshot 创建不可变快照确保可追溯，最后 Active 阶段正式生效到生产环境。

## Section 6: 七阶段建模方法论 (sec-methodology) ~60s

我们的标准建模方法论分七步。第一步源头发现，盘点数据库表和 Schema。第二步 Schema 提取，提取列定义、主键、外键和约束。第三步实体分类，关键判断：有独立主键和实质业务列的归为 ObjectType，两个外键组成复合主键的关联表归为 LinkType。第四步共享属性推断，找出在三张以上表中出现的同名同类型列，提炼为 SharedPropertyType，再组合成 InterfaceType。第五步命名和 RID 生成，按 snake_case 生成 api_name，按 ri 点前缀点 UUID 格式生成唯一标识。第六步详细映射，SQL 类型映射到 Proto DataType，推断校验规则和 UI 配置。第七步 JSON 生成与校验，输出 OntologyRegistry 文件并运行八项交叉引用校验。

## Section 7: 机场实战案例 (sec-airport) ~80s

最后来看机场运营实战案例。假设数据库有九张表：airports、terminals、gates、airlines、flights、passengers、baggage、flight_gate_assignments 和 boarding_passes。

实体分类结果：前七张表都有独立主键和业务列，归为 ObjectType。flight_gate_assignments 由两个外键组成复合主键，归为 LinkType。boarding_passes 同理也是 LinkType。

共享属性推断：iata_code 在三张表出现、status 在五张表出现、created_at 和 updated_at 在所有表出现，全部提炼为 SharedPropertyType。然后组合成接口：created_at 加 updated_at 组成 auditable，name 组成 named_entity，latitude 加 longitude 组成 locatable，status 组成 stateful，再扩展出 schedulable。

最终模型包含七个对象、五个关系、三个动作。关系中，flight_assigned_to_gate 是多对多并携带 assigned_time 属性，passenger_boarded_flight 也是多对多并携带 seat_number 和 boarding_group。动作方面，delay_flight 是 Python 引擎非幂等操作，assign_gate 是原生 CRUD 幂等写入，check_in_passenger 是 Python 引擎非幂等操作。页面最下方的全景图展示了完整的机场 Ontology 图谱。

## Section 8: 结尾 (sec-hero) ~10s

以上就是 DataOS 本体系统的完整概览，从设计哲学到实战建模。希望对你有帮助，感谢收听！
