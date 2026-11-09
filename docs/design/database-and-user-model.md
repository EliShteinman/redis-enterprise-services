# מודל ה-DB והיוזרים

אילו שדות של ה-DB ושל היוזרים השירות חושף, מאיפה כל ערך מגיע, ומה נשאר בחוץ. הטיפוסים והטווחים המדויקים בחוזה
(`contracts/service-api.md` סעיף 3).

**גרסת DB:** Redis 8.4. ה-modules מובנים בגרסה, ולכן `module_list` לא חלק מהמודל.

---

## 1. כללים

- **כל שדה במודל** יכול לקבל ברירת מחדל מ-`config/database_defaults.yaml`: ערכים כלליים, ודריסות שחלות לפי
  תוויות של הקלאסטר (רשת, סביבה, אתר, סוג או שם; `creation.md` סעיף 2). ה-UI יכול לשלוח ערך לכל שדה, והערך שלו
  דורס את ברירת המחדל. שדה שנשלח כ-`null` נחשב כאילו לא נשלח. אין שדה שנקבע רק מהקונפיג.
- **שדות חובה** הם שדות בלי ברירת מחדל: `name` ו-`memory_size`.
- **שדה שלא במודל** לא מגיע מה-UI, והקלאסטר קובע אותו לפי ברירת המחדל שלו. השירות מוסיף לגוף היצירה רק את
  `default_user`, `authentication_redis_pass` ו-`tags` (סעיף 2).
- **שם ה-DB:** תבנית ואורך מקסימלי מ-`config/naming.yaml`, נבדקים לפני הקבלה (`invalid_name`).
- **ברירות המחדל עצמן** עוברות ולידציה מול מודל ה-DB בעליית השירות. ערך לא חוקי עוצר את השירות.

---

## 2. השדות במודל

| שדה | חובה | ברירת מחדל בקונפיג | הערה |
|---|---|---|---|
| `name` | ✅ | - | |
| `memory_size` | ✅ | - | |
| `version` | | `8.4` | |
| `replication` | | `true`, וב-DEV `false` | |
| `sharding` | | | |
| `shards_count` | | | |
| `shard_key_regex` | | | בלי ערך, חלים כללי ברירת המחדל של Redis. רלוונטי רק כש-`sharding` דלוק. השירות לא בודק את זה, והקלאסטר דוחה |
| `data_persistence` | | `aof` | |
| `aof_policy` | | `appendfsync-every-sec` | רק עם `aof`. נשלח רק כש-`data_persistence` הוא `aof` |
| `snapshot_policy` | | `[{secs: 3600, writes: 1}]` | רק עם `snapshot`. הקלאסטר דוחה `snapshot` בלי מדיניות, ולכן יש ברירת מחדל |
| `eviction_policy` | | | ב-AA, eviction מתחיל ב-80% מהזיכרון (תיעוד) |
| `shards_placement` | | `dense` | |
| `proxy_policy` | | `all-master-shards` | |
| `slave_ha` | | | |

**מה השירות מוסיף לגוף היצירה:**
- `default_user: true` ו-`authentication_redis_pass`, עם הסיסמה הקבועה מ-Secret. חיבור בלי סיסמה נדחה (`NOAUTH`),
  וחיבור עם הסיסמה עובד. הסיסמה לא נכנסת לקלט של הצעד ולא ל-saga record: היא ב-`database.secret_fields`, ונמחקת
  מתשובת ה-bdb לפני שהיא נשמרת.
- `tags` מ-`database.default_tags` (היום `[]`). כך השדה קיים תמיד, ועדכון שלו בהמשך יוכל לשמור snapshot.

**מתוכנן (`planned.md`):**
- **עריכה:** כל שדה במודל חוץ מ-`name`. שדות שאי אפשר להחזיר אחורה יהיו ברשימה בקונפיג, והם יקבעו אם צעד העריכה
  הוא pivot. מגבלות של התשתית (הקטנת `shards_count`) נבדקות בקלאסטר, והשגיאה שלו חוזרת.
- **החלפת הסיסמה של `default_user`:** `/v1/bdbs/{uid}/passwords` מוסיף, מחליף או מוחק סיסמה, ואפשר להחזיק שתיים
  במקביל בזמן ההחלפה.
- **AA:** הערכים נשלחים ב-`default_db_config`.

**לא נשלחים, ולא במודל:**
- **`port`:** הקלאסטר מקצה פורט אוטומטית, גם ב-AA.
- **`tls_mode`:** אין TLS. החיבור הוא בשם משתמש וסיסמה בלבד.
- **`roles_permissions`:** ה-Saga בונה אותו מהיוזרים.

---

## 3. AA (מתוכנן): שדות שחייבים להיות זהים בין האתרים

לפי התיעוד של `crdb/database_config`:

| רמה | שדות | מה המודל עושה |
|---|---|---|
| חייבים להיות זהים, אחרת הסנכרון נכשל | `version`, `sharding`, `shard_key_regex` | יחסום ערך שונה בין קלאסטרים בצירוף |
| מומלץ שיהיו זהים | `memory_size`, `eviction_policy`, `shards_count`, `shards_placement`, `proxy_policy` | יזהיר |
| מותר שיהיו שונים | `data_persistence`, `aof_policy`, `snapshot_policy`, `replication` | לא בשימוש. אצלנו הם זהים |

**לא יהיה הבדל בין אתרים, חוץ מהיוזרים.** כל הערכים יישלחו ב-`default_db_config`, ו-`instances[].db_config` לא.
Redis מאפשר הבדלים, אבל השירות לא ישתמש בזה.

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

## 5. יוזר, ACL ו-role

| משאב | שדה | מקור | הערה |
|---|---|---|---|
| ACL | `name` | נגזר: `{db}-{user}-acl` | |
| ACL | `acl` | ה-UI (`users[].acl_rule`), מחרוזת ACL גולמית (למשל `+@all ~*`), לא ריקה | |
| role | `name` | נגזר: `{db}-{user}-role` | |
| role | `management` | קונפיג, ברירת מחדל `db_viewer` | |
| role | `resources` | נגזר: `[{type: db, uids: [ה-DB]}]` | מגביל את ה-role ל-DB של היוזר בלבד |
| user | `name` | ה-UI, חובה | המפתח של היוזר. בלי `-`, וכל שם פעם אחת בבקשה. הקלאסטר אוכף ייחודיות, תלוית רישיות |
| user | `email` | לא נשלח | אין מיילים ליוזרים |
| user | `password` | ה-UI, חובה, לא ריקה | |
| user | `auth_method` | לא נשלח. ברירת המחדל של הקלאסטר היא `regular` | |
| user | `role_uids` | ה-Saga | |

- **יוזר חייב role אחד לפחות.** בלי role הקלאסטר מחזיר `400`. לכן ה-role נוצר לפני היוזר.
- **`email_alerts` של יוזר חדש דלוק כברירת מחדל**. מה לעשות איתו פתוח: `planned.md`.
- **יוזר עם `management: none`** מקבל `403` מה-REST API.
