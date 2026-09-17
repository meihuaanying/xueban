-- 学伴初始化脚本（首次启动 PostgreSQL 容器时自动执行）
-- 1) 为 Langfuse 观测服务创建独立数据库
CREATE DATABASE langfuse;

-- 2) 业务库启用 pgvector 扩展（向量检索）
CREATE EXTENSION IF NOT EXISTS vector;
