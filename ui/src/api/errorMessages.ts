const MESSAGES: Record<string, string> = {
  UNAUTHORIZED: "身份验证失败，请重新登录",
  FORBIDDEN: "当前权限不足以执行此操作",
  NOT_FOUND: "未找到对应资源",
  TURN_IN_FLIGHT: "本会话已有一个进行中的对话轮，请等待其完成",
  STALE_STAGING: "暂存区已被其他操作修改，无法回退（请检查并手动清理）",
  STALE_VERSION: "暂存区版本已变更，请刷新后重试",
  VALIDATION_FAILED: "数据校验未通过",
  REFERENCED: "实体仍被其他实体引用，无法删除",
  FILE_TOO_LARGE: "文件超出大小上限",
  INVALID_BODY: "请求格式不正确",
  WALL_CLOCK_TIMEOUT: "执行超时",
  STEP_CAP_EXCEEDED: "智能体步骤超出上限",
  LLM_PROVIDER_ERROR: "大模型服务返回错误",
  STAGING_LOCKED: "暂存区被锁定",
  TOO_MANY_SESSIONS: "活动会话数已达上限",
};

export function translateError(code: string | undefined): string {
  if (!code) return "未知错误";
  return MESSAGES[code] ?? `未知错误（${code}）`;
}
