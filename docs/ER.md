# PawCare 数据模型（ER）

> 第一版核心表。后续实现 Agent 评测时，评测用例放仓库 YAML，不建库表。

```mermaid
erDiagram
    USERS ||--o{ PETS : owns
    USERS ||--o{ NOTIFICATIONS : receives
    USERS ||--o{ AGENT_CONVERSATIONS : starts
    USERS ||--o{ AUDIT_LOGS : acts
    PETS ||--o{ WEIGHT_RECORDS : has
    PETS ||--o{ HEALTH_RECORDS : has
    PETS ||--o{ REMINDERS : has
    PETS ||--o{ BOARDING_ORDERS : books
    PETS ||--o{ BOARDING_DRAFTS : drafts
    KENNELS ||--o{ BOARDING_ORDERS : hosts
    KENNELS ||--o{ BOARDING_DRAFTS : reserves
    BOARDING_ORDERS ||--o{ BOARDING_DAILY_REPORTS : has
    BOARDING_ORDERS ||--o{ MEDICATION_LOGS : has
    AGENT_CONVERSATIONS ||--o{ AGENT_MESSAGES : has
    AGENT_CONVERSATIONS ||--o{ AGENT_TOOL_CALLS : traces

    USERS {
        int id PK
        string username UK
        string password_hash
        string nickname
        string role
        string phone
        int status
        int token_version
    }

    PETS {
        int id PK
        int owner_id FK
        string name
        string species
        string breed
        date birthday
        string gender
        bool neutered
        text allergies
        text notes
        string photo_url
        string status
    }

    WEIGHT_RECORDS {
        int id PK
        int pet_id FK
        date record_date
        numeric weight_kg
        text note
    }

    HEALTH_RECORDS {
        int id PK
        int pet_id FK
        string record_type
        string title
        date record_date
        date next_due_date
        text note
        json extra
        int created_by FK
        datetime deleted_at
    }

    ATTACHMENTS {
        int id PK
        string owner_type
        int owner_id
        string file_name
        string file_path
        string mime_type
        int size_bytes
        int uploaded_by FK
    }

    KENNELS {
        int id PK
        string code UK
        string size
        string status
        numeric daily_price
        text note
    }

    BOARDING_ORDERS {
        int id PK
        int pet_id FK
        int owner_id FK
        int kennel_id FK
        date start_date
        date end_date
        string status
        numeric daily_price
        numeric deposit
        numeric total_amount
        datetime confirmed_at
        datetime checked_in_at
        datetime checked_out_at
        int created_by FK
    }

    BOARDING_DAILY_REPORTS {
        int id PK
        int order_id FK
        date report_date
        string appetite
        string stool
        string spirit
        text note
        json photos
        int created_by FK
    }

    MEDICATION_LOGS {
        int id PK
        int order_id FK
        string medication_name
        string dose
        datetime given_at
        int given_by FK
        text note
    }

    BOARDING_DRAFTS {
        int id PK
        int owner_id FK
        int pet_id FK
        int kennel_id FK
        date start_date
        date end_date
        numeric daily_price
        numeric total_amount
        string status
        datetime expires_at
        string idempotency_key UK
        int conversation_id FK
        text note
    }

    REMINDERS {
        int id PK
        int pet_id FK
        string reminder_type
        string title
        date due_date
        string status
        string dedupe_key UK
        int source_health_record_id FK
        datetime notified_at
    }

    NOTIFICATIONS {
        int id PK
        int user_id FK
        string title
        text content
        bool is_read
    }

    AGENT_CONVERSATIONS {
        int id PK
        int user_id FK
        string title
        datetime last_message_at
    }

    AGENT_MESSAGES {
        int id PK
        int conversation_id FK
        string role
        text content
        json tool_calls
        string tool_call_id
        string trace_id
    }

    AGENT_TOOL_CALLS {
        int id PK
        string trace_id
        int conversation_id FK
        int message_id FK
        string tool_name
        json arguments
        text result_summary
        string status
        string error_code
        int latency_ms
        int token_in
        int token_out
    }

    KNOWLEDGE_CHUNKS {
        int id PK
        string doc_id
        int chunk_index
        string title
        text content
        vector embedding
        json meta
    }

    AUDIT_LOGS {
        int id PK
        int actor_id FK
        string action
        string target_type
        int target_id
        json before_data
        json after_data
        string trace_id
        string ip
    }
```

## 约束说明

- `boarding_orders` 同一 `kennel_id` 的日期区间不得重叠：MySQL 无 `EXCLUDE` 约束，由应用层档期校验在确认事务中完成，并用笼舍行锁（`SELECT … FOR UPDATE`）串行化并发确认。
- 向量列 `knowledge_chunks.embedding` 以 JSON 文本（512 维）存储，检索在应用层计算余弦相似度。
- `reminders.dedupe_key` 唯一，保证 APScheduler 重复扫描不会产生重复提醒。
- `boarding_drafts.idempotency_key` 唯一，确认接口用它防重复下单。
- 健康档案采用软删除（`deleted_at`），关键修改写 `audit_logs`。
