import { z } from "zod";

/** 全局错误响应契约：{ code, message, trace_id } */
export const ApiErrorSchema = z.object({
  code: z.string().min(1),
  message: z.string().min(1),
  trace_id: z.string().optional(),
});

export type ApiError = z.infer<typeof ApiErrorSchema>;

/** /healthz 健康检查响应契约 */
export const HealthResponseSchema = z.object({
  status: z.literal("ok"),
  service: z.string(),
  version: z.string(),
});

export type HealthResponse = z.infer<typeof HealthResponseSchema>;

/** 分页响应包装 */
export const PaginationSchema = z.object({
  page: z.number().int().positive(),
  page_size: z.number().int().positive().max(100),
  total: z.number().int().nonnegative(),
});

export type Pagination = z.infer<typeof PaginationSchema>;
