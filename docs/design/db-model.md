# מודל ה-DB

**סטטוס:** הוחלט, חוץ מהפריטים בסעיף 5
**תאריך:** 2026-10-21
**גרסת DB:** Redis 8.4. ה-modules מובנים בגרסה, ולכן `module_list` לא חלק מהמודל.

---

## 1. כללים

- **כל שדה במודל** מקבל ברירת מחדל מעץ הקונפיג (global ⇐ סביבה ⇐ רשת ⇐ אתר ⇐ קלאסטר, ראו `saga.md` סעיף 1).
  ה-UI יכול לשלוח ערך לכל שדה, והערך שלו דורס את ברירת המחדל. אין שדה שנקבע רק מהקונפיג.
- **שדות חובה** הם שדות בלי ברירת מחדל: `name` ו-`memory_size`.
- **שדה שלא במודל** לא נשלח לקלאסטר, והקלאסטר קובע אותו לפי ברירת המחדל שלו.

---

## 2. השדות במודל

| שדה | חובה | ברירת מחדל בקונפיג | עריכה | הערה |
|---|---|---|---|---|
| `name` | ✅ | - | ⛔ | המפתח של `find_by_key` ושל שמות ה-ACL וה-role |
| `memory_size` | ✅ | - | ✅ | |
| `version` | | `8.4` | ⛔ | |
| `replication` | | | ✅ | הפיך (V10) |
| `sharding` | | | ⛔ ב-AA | ב-AA לא ניתן להפעלה או לכיבוי אחרי היצירה |
| `shards_count` | | | הגדלה בלבד | הגדלה היא pivot |
| `shard_key_regex` | | כללי ברירת המחדל של Redis | ⛔ ב-AA | נשלח רק כש-`sharding` דלוק |
| `data_persistence` | | `aof` | ✅ | |
| `aof_policy` | | `appendfsync-every-sec` | ✅ | |
| `snapshot_policy` | | | ✅ | רלוונטי רק כש-`data_persistence` הוא `snapshot` |
| `eviction_policy` | | | ✅ | ב-AA, eviction מתחיל ב-80% מהזיכרון (תיעוד) |
| `shards_placement` | | `dense` | ✅ | |
| `proxy_policy` | | `all-master-shards` | ✅ | |
| `slave_ha` | | | ✅ | |

**לא נשלחים, ולא במודל:**
- **`port`:** הקלאסטר מקצה פורט אוטומטית.
- **`tls_mode`:** אין TLS. החיבור הוא בשם משתמש וסיסמה בלבד.
- **`roles_permissions`:** ה-Saga בונה אותו מהיוזרים.

---

## 3. AA: שדות שחייבים להיות זהים בין האתרים

לפי התיעוד של `crdb/database_config`:

| רמה | שדות | מה המודל עושה |
|---|---|---|
| חייבים להיות זהים, אחרת הסנכרון נכשל | `version`, `sharding`, `shard_key_regex` | חוסם ערך שונה בין קלאסטרים בצירוף |
| מומלץ שיהיו זהים | `memory_size`, `eviction_policy`, `shards_count`, `shards_placement`, `proxy_policy` | מזהיר |
| מותר שיהיו שונים | `data_persistence`, `aof_policy`, `snapshot_policy`, `replication` | נשלחים ב-`instances[].db_config` כשהם שונים |

ערך משותף לכל האתרים נשלח ב-`default_db_config`. ערך שונה באתר מסוים נשלח ב-`instances[].db_config` של
אותו אתר (V15).

---

## 4. נשארו מחוץ למודל

- **אבטחה:** TLS ותעודות לקוח, `data_internode_encryption`, mTLS, `disabled_commands`.
- **פריסה:** OSS Cluster, `oss_sharding`, `rack_aware`, `hash_slots_policy`, `avoid_nodes` ו-`use_nodes`.
- **גיבוי ונתונים:** backup, import, export, Replica Of.
- **AA:** `encryption`, `featureset_version`, `crdt_repl_backlog_size`, `crdt_xadd_id_uniqueness_mode`,
  `crdt_syncer_auto_oom_unlatch`.
- **כוונון פנימי:** חיבורים ו-proxy, סנכרון הדרגתי, defrag, pipeline, `maxclients`, `max_connections`,
  `repl_backlog_size`, `slave_buffer`, `max_aof_file_size`, `recovery_wait_time`.
- **הגדרות פנימיות של יכולות:** search, timeseries, probabilistic, `audit_settings`.
- **ברירות מחדל של Redis שלא צריך לשלוח:** `resp3`, `shard_block_foreign_keys`.
- **סוגים אחרים:** memcached, Redis Flex, שדות deprecated, שדות לקריאה בלבד.

---

## 5. פתוח

### להחלטה

| שדה | מה פתוח |
|---|---|
| `tags` | יוחלט בהמשך |
| `email_alerts` | בבדיקה. אם ייכנס, ההתראות יישלחו לכתובת מייל קבועה. |
| **סיסמת ה-default הקבועה** | לכל DB נשלחת סיסמת default קבועה, מ-Secret. עוד לא נבדק באיזה שדה: `authentication_redis_pass` (deprecated, אבל מופיע בדוגמאות של Redis) או המנגנון של כמה סיסמאות. ב-AA לא מומלץ לכבות אותה אחרי היצירה (תיעוד). |
| **פורט אוטומטי ב-AA** | לבדוק שגם ב-CRDB הקלאסטרים מקצים פורט בעצמם. בכל הבדיקות עד עכשיו נשלח פורט. |

### לבדיקה עתידית

| שדה | מה הוא עושה |
|---|---|
| `auto_upgrade` | מעדכן את גרסת ה-DB אוטומטית אחרי שהקלאסטר מתעדכן |
| `master_persistence` | כותב AOF גם ב-master. כרגע ה-master לא כותב. |
| `crdt_causal_consistency` | ב-AA, מבטיח שעדכונים מגיעים לכל האתרים לפי סדר התלות ביניהם |
| `replication_oom_threshold_percent` | ב-AA, מ-8.4: חוסם כתיבות של לקוחות לפני OOM, כדי שהסנכרון בין האתרים ימשיך |
| `instances[].compression` | ב-AA: רמת הדחיסה של הסנכרון בין האתרים (0–6, ברירת מחדל 3) |
| `mkms` | פקודות multi-key על פני כמה shards. ב-AA לא נתמך. |
| `slave_ha_priority` | הסדר שבו DBs מקבלים replica חדשה אחרי נפילת node |
| `metrics_export_all` | מוציא את כל המטריקות של ה-shards ל-Prometheus |
| `query_performance_factor` | מקצה יותר CPU ל-Search בכל shard. ב-8.x משתנה בלי restart. |
