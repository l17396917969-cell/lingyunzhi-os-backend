-- ----------------------------
-- Table structure for daily_plan
-- ----------------------------
DROP TABLE IF EXISTS `daily_plan`;
CREATE TABLE `daily_plan`  (
  `dispatch_no` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '派工号',
  `plan_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '计划状态',
  `model_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '机型',
  `batch_no` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '批次',
  `stage_no` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '架次',
  `station_code` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '站位编码',
  `station_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '站位名称',
  `plan_start_date` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '计划开工日期',
  `plan_end_date` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '计划完工日期',
  `dept_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '所属单位',
  `sync_date` varchar(19) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '计划同步日期',
  `plan_year_month` varchar(7) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '年月'
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '日计划表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of daily_plan
-- ----------------------------
INSERT INTO `daily_plan` VALUES ('DP-20240315-001', '执行中', 'C919', 'B01', 'MS-01', 'ST-101', '机翼对接站', '2024-03-11', '2024-03-19', '总装二厂', '2024-03-10 09:03:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-002', '已完成', 'ARJ21', 'B02', 'MS-02', 'ST-102', '中后机身装配站', '2024-03-12', '2024-03-20', '部装一厂', '2024-03-11 10:06:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-003', '已下达', 'C919', 'B03', 'MS-03', 'ST-103', '总装测试站', '2024-03-13', '2024-03-21', '总装一厂', '2024-03-12 11:09:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-004', '执行中', 'ARJ21', 'B04', 'MS-04', 'ST-104', '机头总装站', '2024-03-14', '2024-03-22', '总装二厂', '2024-03-13 08:12:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-005', '已完成', 'C919', 'B05', 'MS-05', 'ST-105', '机翼对接站', '2024-03-15', '2024-03-23', '部装一厂', '2024-03-14 09:15:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-006', '已下达', 'ARJ21', 'B06', 'MS-06', 'ST-106', '中后机身装配站', '2024-03-16', '2024-03-24', '总装一厂', '2024-03-15 10:18:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-007', '执行中', 'C919', 'B07', 'MS-07', 'ST-107', '总装测试站', '2024-03-17', '2024-03-25', '总装二厂', '2024-03-16 11:21:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-008', '已完成', 'ARJ21', 'B08', 'MS-08', 'ST-108', '机头总装站', '2024-03-18', '2024-03-26', '部装一厂', '2024-03-17 08:24:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-009', '已下达', 'C919', 'B09', 'MS-09', 'ST-109', '机翼对接站', '2024-03-19', '2024-03-27', '总装一厂', '2024-03-18 09:27:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-010', '执行中', 'ARJ21', 'B10', 'MS-10', 'ST-110', '中后机身装配站', '2024-03-20', '2024-03-28', '总装二厂', '2024-03-19 10:30:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-011', '已完成', 'C919', 'B11', 'MS-11', 'ST-111', '总装测试站', '2024-03-21', '2024-03-29', '部装一厂', '2024-03-20 11:33:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-012', '已下达', 'ARJ21', 'B12', 'MS-12', 'ST-112', '机头总装站', '2024-03-22', '2024-03-30', '总装一厂', '2024-03-21 08:36:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-013', '执行中', 'C919', 'B13', 'MS-13', 'ST-113', '机翼对接站', '2024-03-23', '2024-03-31', '总装二厂', '2024-03-22 09:39:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-014', '已完成', 'ARJ21', 'B14', 'MS-14', 'ST-114', '中后机身装配站', '2024-03-24', '2024-03-01', '部装一厂', '2024-03-23 10:42:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-015', '已下达', 'C919', 'B15', 'MS-15', 'ST-115', '总装测试站', '2024-03-25', '2024-03-02', '总装一厂', '2024-03-24 11:45:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-016', '执行中', 'ARJ21', 'B16', 'MS-16', 'ST-116', '机头总装站', '2024-03-26', '2024-03-03', '总装二厂', '2024-03-25 08:48:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-017', '已完成', 'C919', 'B17', 'MS-17', 'ST-117', '机翼对接站', '2024-03-27', '2024-03-04', '部装一厂', '2024-03-26 09:51:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-018', '已下达', 'ARJ21', 'B18', 'MS-18', 'ST-118', '中后机身装配站', '2024-03-28', '2024-03-05', '总装一厂', '2024-03-27 10:54:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-019', '执行中', 'C919', 'B19', 'MS-19', 'ST-119', '总装测试站', '2024-03-29', '2024-03-06', '总装二厂', '2024-03-28 11:57:00', '2024-03');
INSERT INTO `daily_plan` VALUES ('DP-20240315-020', '已完成', 'ARJ21', 'B20', 'MS-20', 'ST-120', '机头总装站', '2024-03-30', '2024-03-07', '部装一厂', '2024-03-29 08:00:00', '2024-03');

-- ----------------------------
-- Table structure for equipment_failure
-- ----------------------------
DROP TABLE IF EXISTS `equipment_failure`;
CREATE TABLE `equipment_failure`  (
  `id_serial` int NULL DEFAULT NULL COMMENT '序号',
  `equipment_no` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备编号',
  `equipment_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备名称',
  `spec` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备规格',
  `model` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备型号',
  `use_dept` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '使用部门',
  `failure_phenomenon` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '故障现象',
  `failure_reason` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '故障原因',
  `repair_requirement` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '修改要求',
  `plan_release_time` varchar(19) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '计划下达时间',
  `project_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '项目状态',
  `finish_time` varchar(19) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '完工时间',
  `confirm_person` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '确认人',
  `is_outsourced` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '是否外协',
  `dispatch_no` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '派工号',
  `failure_category` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '故障类别',
  `failure_level` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '故障程度'
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '设备故障表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of equipment_failure
-- ----------------------------
INSERT INTO `equipment_failure` VALUES (1001, 'EQ-RBT-20211001', '自动喷涂机器人', 'Standard', 'R-2000iC', '喷漆车间', '三轴伺服报警', '线缆老化断裂', '更换三轴动力电缆', '2024-03-06 09:04:00', '维修中', NULL, NULL, 'N', 'DP-20240315-001', '电气故障', '严重');
INSERT INTO `equipment_failure` VALUES (1002, 'EQ-LAS-20221002', '激光切割机', '6kW', 'LC-6020', '钣金车间', '切割面毛刺超差', '聚焦镜片污染', '清洁并校准光路', '2024-03-07 10:08:00', '待处理', NULL, NULL, 'N', 'DP-20240315-002', '控制系统', '紧急');
INSERT INTO `equipment_failure` VALUES (1003, 'EQ-PRS-20231003', '液压压力机', '800T', 'HP-800', '总装车间', '液压站压力波动', '油泵磨损', '更换油泵并排气', '2024-03-08 11:12:00', '已完工', '2024-03-08 17:15:00', '张工', 'N', 'DP-20240315-003', '液压故障', '一般');
INSERT INTO `equipment_failure` VALUES (1004, 'EQ-CNC-20241004', '五轴联动加工中心', '2000x1500', 'G-800', '精加工车间', '主轴异响，温升过高', '润滑系统堵塞', '更换滤网并清洗主轴', '2024-03-09 12:16:00', '维修中', NULL, NULL, 'Y', 'DP-20240315-004', '机械故障', '严重');
INSERT INTO `equipment_failure` VALUES (1005, 'EQ-RBT-20201005', '自动喷涂机器人', 'Standard', 'R-2000iC', '喷漆车间', '三轴伺服报警', '线缆老化断裂', '更换三轴动力电缆', '2024-03-10 13:20:00', '待处理', NULL, NULL, 'N', 'DP-20240315-005', '电气故障', '紧急');
INSERT INTO `equipment_failure` VALUES (1006, 'EQ-LAS-20211006', '激光切割机', '6kW', 'LC-6020', '钣金车间', '切割面毛刺超差', '聚焦镜片污染', '清洁并校准光路', '2024-03-11 08:24:00', '已完工', '2024-03-11 15:30:00', '张工', 'N', 'DP-20240315-006', '控制系统', '一般');
INSERT INTO `equipment_failure` VALUES (1007, 'EQ-PRS-20221007', '液压压力机', '800T', 'HP-800', '总装车间', '液压站压力波动', '油泵磨损', '更换油泵并排气', '2024-03-12 09:28:00', '维修中', NULL, NULL, 'N', 'DP-20240315-007', '液压故障', '严重');
INSERT INTO `equipment_failure` VALUES (1008, 'EQ-CNC-20231008', '五轴联动加工中心', '2000x1500', 'G-800', '精加工车间', '主轴异响，温升过高', '润滑系统堵塞', '更换滤网并清洗主轴', '2024-03-13 10:32:00', '待处理', NULL, NULL, 'Y', 'DP-20240315-008', '机械故障', '紧急');
INSERT INTO `equipment_failure` VALUES (1009, 'EQ-RBT-20241009', '自动喷涂机器人', 'Standard', 'R-2000iC', '喷漆车间', '三轴伺服报警', '线缆老化断裂', '更换三轴动力电缆', '2024-03-14 11:36:00', '已完工', '2024-03-14 18:45:00', '张工', 'N', 'DP-20240315-009', '电气故障', '一般');
INSERT INTO `equipment_failure` VALUES (1010, 'EQ-LAS-20201010', '激光切割机', '6kW', 'LC-6020', '钣金车间', '切割面毛刺超差', '聚焦镜片污染', '清洁并校准光路', '2024-03-15 12:40:00', '维修中', NULL, NULL, 'N', 'DP-20240315-010', '控制系统', '严重');
INSERT INTO `equipment_failure` VALUES (1011, 'EQ-PRS-20211011', '液压压力机', '800T', 'HP-800', '总装车间', '液压站压力波动', '油泵磨损', '更换油泵并排气', '2024-03-16 13:44:00', '待处理', NULL, NULL, 'N', 'DP-20240315-011', '液压故障', '紧急');
INSERT INTO `equipment_failure` VALUES (1012, 'EQ-CNC-20221012', '五轴联动加工中心', '2000x1500', 'G-800', '精加工车间', '主轴异响，温升过高', '润滑系统堵塞', '更换滤网并清洗主轴', '2024-03-17 08:48:00', '已完工', '2024-03-17 16:00:00', '张工', 'Y', 'DP-20240315-012', '机械故障', '一般');
INSERT INTO `equipment_failure` VALUES (1013, 'EQ-RBT-20231013', '自动喷涂机器人', 'Standard', 'R-2000iC', '喷漆车间', '三轴伺服报警', '线缆老化断裂', '更换三轴动力电缆', '2024-03-18 09:52:00', '维修中', NULL, NULL, 'N', 'DP-20240315-013', '电气故障', '严重');
INSERT INTO `equipment_failure` VALUES (1014, 'EQ-LAS-20241014', '激光切割机', '6kW', 'LC-6020', '钣金车间', '切割面毛刺超差', '聚焦镜片污染', '清洁并校准光路', '2024-03-19 10:56:00', '待处理', NULL, NULL, 'N', 'DP-20240315-014', '控制系统', '紧急');
INSERT INTO `equipment_failure` VALUES (1015, 'EQ-PRS-20201015', '液压压力机', '800T', 'HP-800', '总装车间', '液压站压力波动', '油泵磨损', '更换油泵并排气', '2024-03-20 11:00:00', '已完工', '2024-03-20 14:15:00', '张工', 'N', 'DP-20240315-015', '液压故障', '一般');
INSERT INTO `equipment_failure` VALUES (1016, 'EQ-CNC-20211016', '五轴联动加工中心', '2000x1500', 'G-800', '精加工车间', '主轴异响，温升过高', '润滑系统堵塞', '更换滤网并清洗主轴', '2024-03-21 12:04:00', '维修中', NULL, NULL, 'Y', 'DP-20240315-016', '机械故障', '严重');
INSERT INTO `equipment_failure` VALUES (1017, 'EQ-RBT-20221017', '自动喷涂机器人', 'Standard', 'R-2000iC', '喷漆车间', '三轴伺服报警', '线缆老化断裂', '更换三轴动力电缆', '2024-03-22 13:08:00', '待处理', NULL, NULL, 'N', 'DP-20240315-017', '电气故障', '紧急');
INSERT INTO `equipment_failure` VALUES (1018, 'EQ-LAS-20231018', '激光切割机', '6kW', 'LC-6020', '钣金车间', '切割面毛刺超差', '聚焦镜片污染', '清洁并校准光路', '2024-03-23 08:12:00', '已完工', '2024-03-23 17:30:00', '张工', 'N', 'DP-20240315-018', '控制系统', '一般');
INSERT INTO `equipment_failure` VALUES (1019, 'EQ-PRS-20241019', '液压压力机', '800T', 'HP-800', '总装车间', '液压站压力波动', '油泵磨损', '更换油泵并排气', '2024-03-24 09:16:00', '维修中', NULL, NULL, 'N', 'DP-20240315-019', '液压故障', '严重');
INSERT INTO `equipment_failure` VALUES (1020, 'EQ-CNC-20201020', '五轴联动加工中心', '2000x1500', 'G-800', '精加工车间', '主轴异响，温升过高', '润滑系统堵塞', '更换滤网并清洗主轴', '2024-03-25 10:20:00', '待处理', NULL, NULL, 'Y', 'DP-20240315-020', '机械故障', '紧急');

-- ----------------------------
-- Table structure for equipment_ledger
-- ----------------------------
DROP TABLE IF EXISTS `equipment_ledger`;
CREATE TABLE `equipment_ledger`  (
  `equipment_no` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备编号',
  `category_main` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备大类',
  `old_equipment_no` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '原设备编号',
  `equipment_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备名称',
  `spec` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备规格',
  `model` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备型号',
  `weight` decimal(10, 2) NULL DEFAULT NULL COMMENT '设备重量',
  `vendor_name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '供应商名称',
  `manufacturer` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '生产单位名称',
  `origin_country` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '生产厂家国别',
  `factory_no` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '出厂编号',
  `factory_date` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '出厂时间',
  `operation_date` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '投产时间',
  `book_date` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '入账时间',
  `use_dept` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '使用单位',
  `quantity` int NULL DEFAULT NULL COMMENT '数量',
  `unit` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '计量单位',
  `net_value_rate` decimal(5, 2) NULL DEFAULT NULL COMMENT '净值比例',
  `original_value` decimal(18, 4) NULL DEFAULT NULL COMMENT '原值(万)',
  `category_sub` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备类别',
  `area_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '区域名称',
  `location` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '具体位置',
  `power` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备功率',
  `motor_count` int NULL DEFAULT NULL COMMENT '电机台数',
  `is_military_key` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '是否军工关键设备',
  `fund_source` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '资金来源',
  `cnc_category` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '数控分类',
  `cnc_system` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '数控控制系统',
  `equipment_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '设备状态',
  `asset_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '资产状态',
  `is_imported` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '是否进口',
  `remark` text CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL COMMENT '备注',
  `confidential_level` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '数据密级',
  `is_eco_friendly` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '是否环保'
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '设备台账表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of equipment_ledger
-- ----------------------------
INSERT INTO `equipment_ledger` VALUES ('EQ-RBT-2021001', '机器人', 'OLD-001', '自动喷涂机器人', 'Standard', 'R-2000iC', 1200.00, '发那科', 'FANUC', '日本', 'F-2021-0001', '2021-02-02', '2021-02-03', '2021-02-04', '喷漆车间', 1, '台', 0.88, 86.0000, '工业机器人', 'B区', 'B区-02', '12KW', 6, 'N', '国拨', '六轴', 'FANUC R-30iB', '维修中', '在用', 'Y', '常规生产设备', '内部', 'N');
INSERT INTO `equipment_ledger` VALUES ('EQ-LAS-2022002', '切割设备', 'OLD-002', '激光切割机', '6kW', 'LC-6020', 5200.00, '百超', 'Bystronic', '瑞士', 'F-2022-0002', '2022-03-03', '2022-03-04', '2022-03-05', '钣金车间', 1, '台', 0.82, 162.0000, '激光设备', 'C区', 'C区-03', '20KW', 3, 'N', '技改', '二维', 'ByVision', '待保养', '封存', 'Y', '常规生产设备', '秘密', 'Y');
INSERT INTO `equipment_ledger` VALUES ('EQ-PRS-2023003', '压力设备', 'OLD-003', '液压压力机', '800T', 'HP-800', 9800.00, '济二机', 'JIER', '中国', 'F-2023-0003', '2023-04-04', '2023-04-05', '2023-04-06', '总装车间', 1, '台', 0.76, 213.0000, '成形设备', 'D区', 'D区-04', '55KW', 5, 'N', '军品专项', '伺服', 'Bosch Rexroth', '运行中', '在用', 'N', '常规生产设备', '公开', 'N');
INSERT INTO `equipment_ledger` VALUES ('EQ-CNC-2024004', '加工设备', 'OLD-004', '五轴联动加工中心', '2000x1500', 'G-800', 12500.00, '德玛吉', '德玛吉森精机', '德国', 'F-2024-0004', '2020-05-05', '2020-05-06', '2020-05-07', '精加工车间', 1, '台', 0.95, 284.0000, '数控机床', 'A区', 'A区-05', '45KW', 4, 'N', '自筹', '五轴', 'Siemens 840D', '维修中', '在用', 'Y', '关键工序设备', '内部', 'Y');
INSERT INTO `equipment_ledger` VALUES ('EQ-RBT-2020005', '机器人', 'OLD-005', '自动喷涂机器人', 'Standard', 'R-2000iC', 1200.00, '发那科', 'FANUC', '日本', 'F-2020-0005', '2021-06-06', '2021-06-07', '2021-06-08', '喷漆车间', 1, '台', 0.88, 90.0000, '工业机器人', 'B区', 'B区-01', '12KW', 6, 'Y', '国拨', '六轴', 'FANUC R-30iB', '待保养', '封存', 'Y', '常规生产设备', '秘密', 'N');
INSERT INTO `equipment_ledger` VALUES ('EQ-LAS-2021006', '切割设备', 'OLD-006', '激光切割机', '6kW', 'LC-6020', 5200.00, '百超', 'Bystronic', '瑞士', 'F-2021-0006', '2022-07-07', '2022-07-08', '2022-07-09', '钣金车间', 1, '台', 0.82, 166.0000, '激光设备', 'C区', 'C区-02', '20KW', 3, 'N', '技改', '二维', 'ByVision', '运行中', '在用', 'N', '常规生产设备', '公开', 'Y');
INSERT INTO `equipment_ledger` VALUES ('EQ-PRS-2022007', '压力设备', 'OLD-007', '液压压力机', '800T', 'HP-800', 9800.00, '济二机', 'JIER', '中国', 'F-2022-0007', '2023-08-08', '2023-08-09', '2023-08-10', '总装车间', 1, '台', 0.76, 217.0000, '成形设备', 'D区', 'D区-03', '55KW', 5, 'N', '军品专项', '伺服', 'Bosch Rexroth', '维修中', '在用', 'Y', '常规生产设备', '内部', 'N');
INSERT INTO `equipment_ledger` VALUES ('EQ-CNC-2023008', '加工设备', 'OLD-008', '五轴联动加工中心', '2000x1500', 'G-800', 12500.00, '德玛吉', '德玛吉森精机', '德国', 'F-2023-0008', '2020-09-09', '2020-09-10', '2020-09-11', '精加工车间', 1, '台', 0.95, 288.0000, '数控机床', 'A区', 'A区-04', '45KW', 4, 'N', '自筹', '五轴', 'Siemens 840D', '待保养', '封存', 'Y', '关键工序设备', '秘密', 'Y');
INSERT INTO `equipment_ledger` VALUES ('EQ-RBT-2024009', '机器人', 'OLD-009', '自动喷涂机器人', 'Standard', 'R-2000iC', 1200.00, '发那科', 'FANUC', '日本', 'F-2024-0009', '2021-10-10', '2021-10-11', '2021-10-12', '喷漆车间', 1, '台', 0.88, 94.0000, '工业机器人', 'B区', 'B区-05', '12KW', 6, 'N', '国拨', '六轴', 'FANUC R-30iB', '运行中', '在用', 'N', '常规生产设备', '公开', 'N');
INSERT INTO `equipment_ledger` VALUES ('EQ-LAS-2020010', '切割设备', 'OLD-010', '激光切割机', '6kW', 'LC-6020', 5200.00, '百超', 'Bystronic', '瑞士', 'F-2020-0010', '2022-11-11', '2022-11-12', '2022-11-13', '钣金车间', 1, '台', 0.82, 170.0000, '激光设备', 'C区', 'C区-01', '20KW', 3, 'Y', '技改', '二维', 'ByVision', '维修中', '在用', 'Y', '常规生产设备', '内部', 'Y');
INSERT INTO `equipment_ledger` VALUES ('EQ-PRS-2021011', '压力设备', 'OLD-011', '液压压力机', '800T', 'HP-800', 9800.00, '济二机', 'JIER', '中国', 'F-2021-0011', '2023-12-12', '2023-12-13', '2023-12-14', '总装车间', 1, '台', 0.76, 221.0000, '成形设备', 'D区', 'D区-02', '55KW', 5, 'N', '军品专项', '伺服', 'Bosch Rexroth', '待保养', '封存', 'Y', '常规生产设备', '秘密', 'N');
INSERT INTO `equipment_ledger` VALUES ('EQ-CNC-2022012', '加工设备', 'OLD-012', '五轴联动加工中心', '2000x1500', 'G-800', 12500.00, '德玛吉', '德玛吉森精机', '德国', 'F-2022-0012', '2020-01-13', '2020-01-14', '2020-01-15', '精加工车间', 1, '台', 0.95, 292.0000, '数控机床', 'A区', 'A区-03', '45KW', 4, 'N', '自筹', '五轴', 'Siemens 840D', '运行中', '在用', 'N', '关键工序设备', '公开', 'Y');
INSERT INTO `equipment_ledger` VALUES ('EQ-RBT-2023013', '机器人', 'OLD-013', '自动喷涂机器人', 'Standard', 'R-2000iC', 1200.00, '发那科', 'FANUC', '日本', 'F-2023-0013', '2021-02-14', '2021-02-15', '2021-02-16', '喷漆车间', 1, '台', 0.88, 98.0000, '工业机器人', 'B区', 'B区-04', '12KW', 6, 'N', '国拨', '六轴', 'FANUC R-30iB', '维修中', '在用', 'Y', '常规生产设备', '内部', 'N');
INSERT INTO `equipment_ledger` VALUES ('EQ-LAS-2024014', '切割设备', 'OLD-014', '激光切割机', '6kW', 'LC-6020', 5200.00, '百超', 'Bystronic', '瑞士', 'F-2024-0014', '2022-03-15', '2022-03-16', '2022-03-17', '钣金车间', 1, '台', 0.82, 174.0000, '激光设备', 'C区', 'C区-05', '20KW', 3, 'N', '技改', '二维', 'ByVision', '待保养', '封存', 'Y', '常规生产设备', '秘密', 'Y');
INSERT INTO `equipment_ledger` VALUES ('EQ-PRS-2020015', '压力设备', 'OLD-015', '液压压力机', '800T', 'HP-800', 9800.00, '济二机', 'JIER', '中国', 'F-2020-0015', '2023-04-16', '2023-04-17', '2023-04-18', '总装车间', 1, '台', 0.76, 225.0000, '成形设备', 'D区', 'D区-01', '55KW', 5, 'Y', '军品专项', '伺服', 'Bosch Rexroth', '运行中', '在用', 'N', '常规生产设备', '公开', 'N');
INSERT INTO `equipment_ledger` VALUES ('EQ-CNC-2021016', '加工设备', 'OLD-016', '五轴联动加工中心', '2000x1500', 'G-800', 12500.00, '德玛吉', '德玛吉森精机', '德国', 'F-2021-0016', '2020-05-17', '2020-05-18', '2020-05-19', '精加工车间', 1, '台', 0.95, 296.0000, '数控机床', 'A区', 'A区-02', '45KW', 4, 'N', '自筹', '五轴', 'Siemens 840D', '维修中', '在用', 'Y', '关键工序设备', '内部', 'Y');
INSERT INTO `equipment_ledger` VALUES ('EQ-RBT-2022017', '机器人', 'OLD-017', '自动喷涂机器人', 'Standard', 'R-2000iC', 1200.00, '发那科', 'FANUC', '日本', 'F-2022-0017', '2021-06-18', '2021-06-19', '2021-06-20', '喷漆车间', 1, '台', 0.88, 102.0000, '工业机器人', 'B区', 'B区-03', '12KW', 6, 'N', '国拨', '六轴', 'FANUC R-30iB', '待保养', '封存', 'Y', '常规生产设备', '秘密', 'N');
INSERT INTO `equipment_ledger` VALUES ('EQ-LAS-2023018', '切割设备', 'OLD-018', '激光切割机', '6kW', 'LC-6020', 5200.00, '百超', 'Bystronic', '瑞士', 'F-2023-0018', '2022-07-19', '2022-07-20', '2022-07-21', '钣金车间', 1, '台', 0.82, 178.0000, '激光设备', 'C区', 'C区-04', '20KW', 3, 'N', '技改', '二维', 'ByVision', '运行中', '在用', 'N', '常规生产设备', '公开', 'Y');
INSERT INTO `equipment_ledger` VALUES ('EQ-PRS-2024019', '压力设备', 'OLD-019', '液压压力机', '800T', 'HP-800', 9800.00, '济二机', 'JIER', '中国', 'F-2024-0019', '2023-08-20', '2023-08-21', '2023-08-22', '总装车间', 1, '台', 0.76, 229.0000, '成形设备', 'D区', 'D区-05', '55KW', 5, 'N', '军品专项', '伺服', 'Bosch Rexroth', '维修中', '在用', 'Y', '常规生产设备', '内部', 'N');
INSERT INTO `equipment_ledger` VALUES ('EQ-CNC-2020020', '加工设备', 'OLD-020', '五轴联动加工中心', '2000x1500', 'G-800', 12500.00, '德玛吉', '德玛吉森精机', '德国', 'F-2020-0020', '2020-09-21', '2020-09-22', '2020-09-23', '精加工车间', 1, '台', 0.95, 300.0000, '数控机床', 'A区', 'A区-01', '45KW', 4, 'Y', '自筹', '五轴', 'Siemens 840D', '待保养', '封存', 'Y', '关键工序设备', '秘密', 'Y');

-- ----------------------------
-- Table structure for kitting_details
-- ----------------------------
DROP TABLE IF EXISTS `kitting_details`;
CREATE TABLE `kitting_details`  (
  `delivery_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '配送状态',
  `workshop` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '使用车间',
  `model_type` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '机型',
  `stage_no` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '架次',
  `station_code` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '站位编码',
  `station_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '站位名称',
  `process_no` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '工序号',
  `process_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '工序名称',
  `material_no` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '物料号',
  `material_name` varchar(200) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '物料名称',
  `plan_qty` decimal(18, 4) NULL DEFAULT NULL COMMENT '计划数量',
  `alloc_qty` decimal(18, 4) NULL DEFAULT NULL COMMENT '分配数量',
  `picked_qty` decimal(18, 4) NULL DEFAULT NULL COMMENT '已拣数量',
  `ship_qty` decimal(18, 4) NULL DEFAULT NULL COMMENT '发货数量',
  `shortage_qty` decimal(18, 4) NULL DEFAULT NULL COMMENT '缺件数量'
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '配套明细表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of kitting_details
-- ----------------------------
INSERT INTO `kitting_details` VALUES ('配送中', '总装二厂', 'C919', 'MS-01', 'ST-101', '机翼对接站', 'OP-B01', '起落架支架安装', 'MAT-7001', '高强度螺栓 M12', 110.0000, 105.0000, 102.0000, 102.0000, 5.0000);
INSERT INTO `kitting_details` VALUES ('缺件', '部装一厂', 'ARJ21', 'MS-02', 'ST-102', '中后机身装配站', 'OP-C02', '舱门装配', 'MAT-7002', '铝合金支架', 120.0000, 110.0000, 104.0000, 94.0000, 20.0000);
INSERT INTO `kitting_details` VALUES ('已发货', '总装一厂', 'C919', 'MS-03', 'ST-103', '机头总装站', 'OP-D03', '线缆敷设', 'MAT-7003', '航插线束', 130.0000, 115.0000, 115.0000, 115.0000, 15.0000);
INSERT INTO `kitting_details` VALUES ('配送中', '总装二厂', 'ARJ21', 'MS-04', 'ST-104', '机翼对接站', 'OP-E04', '驾驶舱蒙皮铆接', 'MAT-7004', '航空专用铆钉', 140.0000, 140.0000, 137.0000, 137.0000, 0.0000);
INSERT INTO `kitting_details` VALUES ('缺件', '部装一厂', 'C919', 'MS-05', 'ST-105', '中后机身装配站', 'OP-A05', '起落架支架安装', 'MAT-7005', '高强度螺栓 M12', 150.0000, 145.0000, 139.0000, 129.0000, 15.0000);
INSERT INTO `kitting_details` VALUES ('已发货', '总装一厂', 'ARJ21', 'MS-06', 'ST-106', '机头总装站', 'OP-B06', '舱门装配', 'MAT-7006', '铝合金支架', 160.0000, 150.0000, 150.0000, 150.0000, 10.0000);
INSERT INTO `kitting_details` VALUES ('配送中', '总装二厂', 'C919', 'MS-07', 'ST-107', '机翼对接站', 'OP-C07', '线缆敷设', 'MAT-7007', '航插线束', 170.0000, 155.0000, 152.0000, 152.0000, 15.0000);
INSERT INTO `kitting_details` VALUES ('缺件', '部装一厂', 'ARJ21', 'MS-08', 'ST-108', '中后机身装配站', 'OP-D08', '驾驶舱蒙皮铆接', 'MAT-7008', '航空专用铆钉', 180.0000, 180.0000, 174.0000, 164.0000, 10.0000);
INSERT INTO `kitting_details` VALUES ('已发货', '总装一厂', 'C919', 'MS-09', 'ST-109', '机头总装站', 'OP-E09', '起落架支架安装', 'MAT-7009', '高强度螺栓 M12', 190.0000, 185.0000, 185.0000, 185.0000, 5.0000);
INSERT INTO `kitting_details` VALUES ('配送中', '总装二厂', 'ARJ21', 'MS-10', 'ST-110', '机翼对接站', 'OP-A10', '舱门装配', 'MAT-7010', '铝合金支架', 200.0000, 190.0000, 187.0000, 187.0000, 10.0000);
INSERT INTO `kitting_details` VALUES ('缺件', '部装一厂', 'C919', 'MS-11', 'ST-111', '中后机身装配站', 'OP-B11', '线缆敷设', 'MAT-7011', '航插线束', 210.0000, 195.0000, 189.0000, 179.0000, 25.0000);
INSERT INTO `kitting_details` VALUES ('已发货', '总装一厂', 'ARJ21', 'MS-12', 'ST-112', '机头总装站', 'OP-C12', '驾驶舱蒙皮铆接', 'MAT-7012', '航空专用铆钉', 220.0000, 220.0000, 220.0000, 220.0000, 0.0000);
INSERT INTO `kitting_details` VALUES ('配送中', '总装二厂', 'C919', 'MS-13', 'ST-113', '机翼对接站', 'OP-D13', '起落架支架安装', 'MAT-7013', '高强度螺栓 M12', 230.0000, 225.0000, 222.0000, 222.0000, 5.0000);
INSERT INTO `kitting_details` VALUES ('缺件', '部装一厂', 'ARJ21', 'MS-14', 'ST-114', '中后机身装配站', 'OP-E14', '舱门装配', 'MAT-7014', '铝合金支架', 240.0000, 230.0000, 224.0000, 214.0000, 20.0000);
INSERT INTO `kitting_details` VALUES ('已发货', '总装一厂', 'C919', 'MS-15', 'ST-115', '机头总装站', 'OP-A15', '线缆敷设', 'MAT-7015', '航插线束', 250.0000, 235.0000, 235.0000, 235.0000, 15.0000);
INSERT INTO `kitting_details` VALUES ('配送中', '总装二厂', 'ARJ21', 'MS-16', 'ST-116', '机翼对接站', 'OP-B16', '驾驶舱蒙皮铆接', 'MAT-7016', '航空专用铆钉', 260.0000, 260.0000, 257.0000, 257.0000, 0.0000);
INSERT INTO `kitting_details` VALUES ('缺件', '部装一厂', 'C919', 'MS-17', 'ST-117', '中后机身装配站', 'OP-C17', '起落架支架安装', 'MAT-7017', '高强度螺栓 M12', 270.0000, 265.0000, 259.0000, 249.0000, 15.0000);
INSERT INTO `kitting_details` VALUES ('已发货', '总装一厂', 'ARJ21', 'MS-18', 'ST-118', '机头总装站', 'OP-D18', '舱门装配', 'MAT-7018', '铝合金支架', 280.0000, 270.0000, 270.0000, 270.0000, 10.0000);
INSERT INTO `kitting_details` VALUES ('配送中', '总装二厂', 'C919', 'MS-19', 'ST-119', '机翼对接站', 'OP-E19', '线缆敷设', 'MAT-7019', '航插线束', 290.0000, 275.0000, 272.0000, 272.0000, 15.0000);
INSERT INTO `kitting_details` VALUES ('缺件', '部装一厂', 'ARJ21', 'MS-20', 'ST-120', '中后机身装配站', 'OP-A20', '驾驶舱蒙皮铆接', 'MAT-7020', '航空专用铆钉', 300.0000, 300.0000, 294.0000, 284.0000, 10.0000);

-- ----------------------------
-- Table structure for kitting_plan
-- ----------------------------
DROP TABLE IF EXISTS `kitting_plan`;
CREATE TABLE `kitting_plan`  (
  `plan_status` varchar(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '计划状态',
  `priority` int NULL DEFAULT NULL COMMENT '优先级',
  `dept_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '所属单位',
  `model_code` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '机型编码',
  `dispatch_no` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '派工号',
  `stage_no` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '架次',
  `station_no` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '站位编号',
  `station_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '站位名称',
  `process_code` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '工序编码',
  `process_name` varchar(100) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '工序名称',
  `plan_pick_date` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '计划分拣日期',
  `plan_demand_date` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '计划需求日期',
  `actual_pick_date` varchar(10) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '实际分拣日期',
  `item_count` int NULL DEFAULT NULL COMMENT '配套项数',
  `is_shortage` char(1) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '是否缺件(Y/N)',
  `storage_location` varchar(50) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NULL DEFAULT NULL COMMENT '暂存区库位'
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_0900_ai_ci COMMENT = '配套计划表' ROW_FORMAT = Dynamic;

-- ----------------------------
-- Records of kitting_plan
-- ----------------------------
INSERT INTO `kitting_plan` VALUES ('分拣中', 2, '总装二厂', 'ARJ21-G03', 'DP-20240315-001', 'MS-01', 'ST-101', '机翼对接站', 'OP-B01', '起落架支架安装', '2024-03-11', '2024-03-12', NULL, 7, 'N', 'B-01-02');
INSERT INTO `kitting_plan` VALUES ('待分拣', 3, '部装一厂', 'C929-X02', 'DP-20240315-002', 'MS-02', 'ST-102', '中后机身装配站', 'OP-C02', '舱门装配', '2024-03-12', '2024-03-13', NULL, 8, 'N', 'C-02-04');
INSERT INTO `kitting_plan` VALUES ('已分拣', 4, '总装一厂', 'C919-C01', 'DP-20240315-003', 'MS-03', 'ST-103', '机头总装站', 'OP-D03', '线缆敷设', '2024-03-13', '2024-03-14', '2024-03-13', 9, 'N', 'A-03-06');
INSERT INTO `kitting_plan` VALUES ('分拣中', 5, '总装二厂', 'ARJ21-G03', 'DP-20240315-004', 'MS-04', 'ST-104', '机翼对接站', 'OP-E04', '驾驶舱蒙皮铆接', '2024-03-14', '2024-03-15', NULL, 10, 'Y', 'B-04-08');
INSERT INTO `kitting_plan` VALUES ('待分拣', 1, '部装一厂', 'C929-X02', 'DP-20240315-005', 'MS-05', 'ST-105', '中后机身装配站', 'OP-A05', '起落架支架安装', '2024-03-15', '2024-03-16', NULL, 11, 'N', 'C-05-10');
INSERT INTO `kitting_plan` VALUES ('已分拣', 2, '总装一厂', 'C919-C01', 'DP-20240315-006', 'MS-06', 'ST-106', '机头总装站', 'OP-B06', '舱门装配', '2024-03-16', '2024-03-17', '2024-03-16', 12, 'N', 'A-06-12');
INSERT INTO `kitting_plan` VALUES ('分拣中', 3, '总装二厂', 'ARJ21-G03', 'DP-20240315-007', 'MS-07', 'ST-107', '机翼对接站', 'OP-C07', '线缆敷设', '2024-03-17', '2024-03-18', NULL, 13, 'N', 'B-07-14');
INSERT INTO `kitting_plan` VALUES ('待分拣', 4, '部装一厂', 'C929-X02', 'DP-20240315-008', 'MS-08', 'ST-108', '中后机身装配站', 'OP-D08', '驾驶舱蒙皮铆接', '2024-03-18', '2024-03-19', NULL, 14, 'Y', 'C-08-16');
INSERT INTO `kitting_plan` VALUES ('已分拣', 5, '总装一厂', 'C919-C01', 'DP-20240315-009', 'MS-09', 'ST-109', '机头总装站', 'OP-E09', '起落架支架安装', '2024-03-19', '2024-03-20', '2024-03-19', 15, 'N', 'A-09-18');
INSERT INTO `kitting_plan` VALUES ('分拣中', 1, '总装二厂', 'ARJ21-G03', 'DP-20240315-010', 'MS-10', 'ST-110', '机翼对接站', 'OP-A10', '舱门装配', '2024-03-20', '2024-03-21', NULL, 16, 'N', 'B-00-00');
INSERT INTO `kitting_plan` VALUES ('待分拣', 2, '部装一厂', 'C929-X02', 'DP-20240315-011', 'MS-11', 'ST-111', '中后机身装配站', 'OP-B11', '线缆敷设', '2024-03-21', '2024-03-22', NULL, 17, 'N', 'C-01-02');
INSERT INTO `kitting_plan` VALUES ('已分拣', 3, '总装一厂', 'C919-C01', 'DP-20240315-012', 'MS-12', 'ST-112', '机头总装站', 'OP-C12', '驾驶舱蒙皮铆接', '2024-03-22', '2024-03-23', '2024-03-22', 6, 'Y', 'A-02-04');
INSERT INTO `kitting_plan` VALUES ('分拣中', 4, '总装二厂', 'ARJ21-G03', 'DP-20240315-013', 'MS-13', 'ST-113', '机翼对接站', 'OP-D13', '起落架支架安装', '2024-03-23', '2024-03-24', NULL, 7, 'N', 'B-03-06');
INSERT INTO `kitting_plan` VALUES ('待分拣', 5, '部装一厂', 'C929-X02', 'DP-20240315-014', 'MS-14', 'ST-114', '中后机身装配站', 'OP-E14', '舱门装配', '2024-03-24', '2024-03-25', NULL, 8, 'N', 'C-04-08');
INSERT INTO `kitting_plan` VALUES ('已分拣', 1, '总装一厂', 'C919-C01', 'DP-20240315-015', 'MS-15', 'ST-115', '机头总装站', 'OP-A15', '线缆敷设', '2024-03-25', '2024-03-26', '2024-03-25', 9, 'N', 'A-05-10');
INSERT INTO `kitting_plan` VALUES ('分拣中', 2, '总装二厂', 'ARJ21-G03', 'DP-20240315-016', 'MS-16', 'ST-116', '机翼对接站', 'OP-B16', '驾驶舱蒙皮铆接', '2024-03-26', '2024-03-27', NULL, 10, 'Y', 'B-06-12');
INSERT INTO `kitting_plan` VALUES ('待分拣', 3, '部装一厂', 'C929-X02', 'DP-20240315-017', 'MS-17', 'ST-117', '中后机身装配站', 'OP-C17', '起落架支架安装', '2024-03-27', '2024-03-28', NULL, 11, 'N', 'C-07-14');
INSERT INTO `kitting_plan` VALUES ('已分拣', 4, '总装一厂', 'C919-C01', 'DP-20240315-018', 'MS-18', 'ST-118', '机头总装站', 'OP-D18', '舱门装配', '2024-03-28', '2024-03-29', '2024-03-28', 12, 'N', 'A-08-16');
INSERT INTO `kitting_plan` VALUES ('分拣中', 5, '总装二厂', 'ARJ21-G03', 'DP-20240315-019', 'MS-19', 'ST-119', '机翼对接站', 'OP-E19', '线缆敷设', '2024-03-29', '2024-03-30', NULL, 13, 'N', 'B-09-18');
INSERT INTO `kitting_plan` VALUES ('待分拣', 1, '部装一厂', 'C929-X02', 'DP-20240315-020', 'MS-20', 'ST-120', '中后机身装配站', 'OP-A20', '驾驶舱蒙皮铆接', '2024-03-30', '2024-03-31', NULL, 14, 'Y', 'C-00-00');
