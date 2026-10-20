# חוזה: השירות שלנו ⇐ שירות הקצה

**סטטוס:** טיוטה
**תאריך:** 2026-10-20

המסמך מגדיר מה redis-enterprise-services מצפה לקבל משירות הקצה (cluster-relay, או ה-proxy הזמני). השירות שלנו
נבנה לפי החוזה הזה. ההתאמה של שירות הקצה אליו נעשית בנפרד, באחריות הבעלים שלו.

שמות ה-headers וקודי השגיאה שמופיעים כאן הם הצעה. בשירות שלנו הם נטענים מהקונפיגורציה, ולכן אפשר להחליף
אותם בלי שינוי קוד.

---

## 1. הבקשה

### יעד ואימות מול חומת האש

שירות הקצה נמצא ברשת היעד, מאחורי חומת האש של החברה. חומת האש דורשת אימות בכל בקשה לפני שהיא מעבירה אותה.

| # | דרישה |
|---|---|
| C0a | לכל רשת יש כתובת משלה לשירות הקצה (IP, פורט, route), מקובץ הקונפיגורציה |
| C0b | כל בקשה נושאת את פרטי האימות של חומת האש של אותה רשת: שם משתמש וסיסמה קבועים לכל רשת, מ-Secret |
| C0c | אימות חומת האש נפרד מ-`x-cluster-authorization`, ולא מתנגש בו. שם ה-header והפורמט מהקונפיגורציה. |

### הבקשה עצמה

השירות שלנו שולח בקשה אחת לכל קריאה ל-REST API של קלאסטר:

```
POST /<route>
<header האימות של חומת האש>: <פרטי הרשת>
x-cluster-method: PUT
x-cluster-url: https://<cluster>:9443/v1/bdbs/7?dry_run=1
x-cluster-authorization: Basic <credentials>
traceparent: 00-<trace-id>-<span-id>-01
content-type: application/json
cluster-state-id: 155          (אופציונלי)
x-task-id: <uuid>              (אופציונלי)
x-result-ttl: 3600             (אופציונלי)

<body, כמו שהוא>
```

| # | דרישה | למה |
|---|---|---|
| C1 | ה-URL, כולל query string (`dry_run`, `fields`, `extended`), מועבר לקלאסטר כמו שהוא | בדיקה מוקדמת ושליפות |
| C2 | ה-body מועבר כמו שהוא | |
| C3 | `traceparent` ממשיך לקלאסטר ומוחזר בתשובה | מעקב. גם מזהה הבקשה אצלנו |
| C4 | **`cluster-state-id` מועבר לקלאסטר** כ-request header, אם נשלח | עדכון מותנה של DB. בלעדיו עדכון במקביל דורס שינויים (design סעיף 10) |
| C5 | **`x-task-id` ו-`x-result-ttl` מועברים לקלאסטר**, אם נשלחו | מזהה task של CRDB שאנחנו קובעים, כדי לברר מה קרה אחרי timeout (design סעיף 3) |

**מצב נוכחי ב-cluster-relay:** `outgoing_headers` מעביר רק `authorization`, `content-type` ו-`traceparent`. C4 ו-C5 חסרים.

---

## 2. תשובה מהקלאסטר

| # | דרישה | למה |
|---|---|---|
| C6 | ה-status, ה-headers וה-body של הקלאסטר מוחזרים בלי שינוי, **גם בשגיאה** (4xx/5xx) | ה-Saga מחליט לפי ה-status ולפי `error_code` של הקלאסטר |
| C7 | **`cluster-state-id`** מוחזר כ-response header | נדרש לעדכון המותנה הבא |
| C8 | ה-schema וה-ignored fields מאפשרים את כל התשובות שהשירות שלנו צריך | אחרת תשובה תקינה נחסמת. הרשימה בסעיף 4 |

**מצב נוכחי ב-cluster-relay:** C6 ו-C7 מתקיימים, כי כל ה-headers חוזרים חוץ מ-content-length ודומיו. C8 תלוי בקובץ
ה-schema שיוגדר.

---

## 3. שגיאה ששירות הקצה עצמו יצר

השירות שלנו צריך להבחין בין שגיאה של הקלאסטר לבין שגיאה של שירות הקצה. לדוגמה, 502 יכול להגיע משניהם.

| # | דרישה |
|---|---|
| C9 | **כל** תשובה ששירות הקצה יצר בעצמו (ולא העביר מהקלאסטר) כוללת את ה-header `x-edge-error` עם קוד השגיאה. תשובה שהגיעה מהקלאסטר **לעולם** לא כוללת אותו. |
| C10 | הקודים מבחינים בין מה שבוודאות לא הגיע לקלאסטר לבין מה שאולי בוצע בו (טבלה למטה) |
| C11 | ב-`response_rejected` מוחזר גם ה-status המקורי של הקלאסטר, ב-header `x-edge-cluster-status` |

| `x-edge-error` | מתי | הבקשה הגיעה לקלאסטר? | מה השירות שלנו עושה |
|---|---|---|---|
| `invalid_request` | חסר header או header לא תקין | **לא** | שגיאה אצלנו, לא מנסים שוב |
| `connection_failed` | לא נפתח חיבור לקלאסטר (DNS, connection refused) | **לא** | הצעד נכשל. אפשר לנסות שוב בבטחה |
| `timeout` | הבקשה נשלחה, ולא חזרה תשובה בזמן | **לא ידוע** | `find_by_key` (design סעיף 3) |
| `response_rejected` | הקלאסטר ענה, והתשובה לא עמדה ב-schema | **כן**. ה-status המקורי ב-`x-edge-cluster-status` | 2xx מקורי על כתיבה ⇐ הפעולה בוצעה, `find_by_key` מביא את ה-uid |

**מצב נוכחי ב-cluster-relay:**
- **C9:** אין header שמסמן שגיאה של שירות הקצה.
- **C10:** `cluster_unreachable` מאחד את `connection_failed` ואת `timeout`.
- **C11:** ה-status המקורי לא מוחזר ב-`response_rejected`.

---

## 4. תשובות שה-schema חייב לאפשר (C8)

| endpoint | שיטה | תשובה |
|---|---|---|
| `/v1/bdbs`, `/v1/bdbs/{uid}` | GET, POST, PUT, DELETE (כולל `dry_run`) | אובייקט bdb או רשימה |
| `/v1/redis_acls[/{uid}]` | GET, POST, PUT, DELETE | ACL או רשימה. ב-DELETE: `{action_uid}` |
| `/v1/roles[/{uid}]` | GET, POST, PUT, DELETE | role או רשימה. ב-DELETE: `{action_uid}` |
| `/v1/users[/{uid}]` | GET, POST, PUT, DELETE | user או רשימה |
| `/v1/users/password` | POST, PUT, DELETE | גוף ריק או הודעה |
| `/v1/crdbs[/{guid}]` | GET, POST, PATCH, DELETE | crdb, או crdb task |
| `/v1/crdb_tasks/{id}` | GET, POST `actions/cancel` | crdb task |
| `/v1/actions/{uid}` | GET | action |
| `/v1/cluster` | GET | אובייקט cluster (FQDN) |
| `/v1/cluster/stats/last` | GET | סטטיסטיקות (`provisional_memory`) |
| כל endpoint | כל שיטה | גוף שגיאה של הקלאסטר: `{error_code, description}` |
| כל endpoint | כל שיטה | **קריאה ישירה:** כל תשובה, כי היא לא מוגבלת |

---

## 5. סודות

| # | דרישה | למה |
|---|---|---|
| C12 | שירות הקצה לא רושם ללוג את `x-cluster-authorization` | |
| C13 | שירות הקצה לא רושם ללוג סודות מתוך גוף התשובה, ובכלל זה ב-failure log | תשובות bdb כוללות `authentication_admin_pass` (נבדק) |
| C14 | שירות הקצה לא רושם ללוג את גוף הבקשה של `POST /v1/crdbs`, `POST/PUT /v1/users` ו-`/v1/users/password` | הם כוללים סיסמאות של קלאסטרים ושל יוזרים |

**מצב נוכחי ב-cluster-relay:** ה-failure log כותב את התשובה המלאה של הקלאסטר. C13 לא מתקיים.

---

## 6. סיכום: מה חסר ב-cluster-relay

| # | מה | חומרה |
|---|---|---|
| C4 | העברת `cluster-state-id` לקלאסטר | גבוהה: בלי זה אין עדכון מותנה |
| C5 | העברת `x-task-id` ו-`x-result-ttl` | גבוהה ל-AA |
| C9 | header שמסמן שגיאה של שירות הקצה | גבוהה |
| C10 | פיצול `cluster_unreachable` ל-`connection_failed` ו-`timeout` | גבוהה |
| C11 | ה-status המקורי ב-`response_rejected` | בינונית |
| C13 | הסתרת סודות ב-failure log | גבוהה (אבטחה) |
| C8 | schema שמאפשר את כל התשובות בסעיף 4 | תלוי בקובץ ה-schema |
