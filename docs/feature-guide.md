# Feature Guide: Use Every Feature, Click by Click

> Before starting: backend and dashboard running ([setup.md](setup.md)), and an admin user created:
> `python -m app.cli create-user admin --role admin` (from `backend/`).
> Open **http://localhost:5173**.

## 1. Log in
1. Type your username and password, then click **Sign in**.
2. Try a wrong password: you see "Incorrect username or password". It's the same message whether the user exists or not, on purpose.
3. **Behind the scenes:**
   - the password is checked against its Argon2 hash;
   - you get a 30-minute token;
   - the attempt is written to the audit log and recorded as an event.

## 2. Create an attack and watch AEGIS catch it (Simulator)
1. Click **Simulator** in the sidebar.
2. On **Account takeover**, click **Run scenario**. Six events are sent one by one: 4 failed logins, a success, then a permission change.
3. The result shows:
   - **AUTH-002** (failed logins followed by success);
   - **ACCOUNT-001** (sensitive change);
   - one **incident** grouping both.
4. Click the incident. You land on its detail page (section 4).
5. Run **Normal user**: it should create **no** detections. That checks for false alarms.
6. Run **Password guessing**: watch **AUTH-001** and **ML-001** appear together (rule and model agree).

## 3. See what needs attention (Overview)
- **Active incidents** by severity, and how many have **no one assigned**.
- **Detections in the last 24 h** by rule: click a rule to see its detections.
- **Newest open incidents**: click one to open it.

## 4. Investigate an incident (Incident detail)
1. **Why these were grouped**: the correlation reason. Same account, each detection within 1 hour of the last activity.
2. **Detections**: each with its rule, severity, `Rule` or `ML · score` badge, and the explanation sentence.
3. **Timeline**: every evidence event in time order. Failures and denials have a red edge.
4. **Actions** (right side):
   - **Assign to me**: the incident shows your name; the history records it.
   - **Mark acknowledged** → **Mark investigating**. Only valid next steps are shown.
   - **Resolve…**: pick a conclusion (True positive / False positive / Benign / Duplicate), optionally write what you found, then **Resolve incident**.
   - **Mark closed**: final. After that, no more changes or notes.
   - **Reopen** (from resolved): the old conclusion is cleared, but stays visible in the history.
5. **Notes**: write what you checked and found, then **Add note**. Notes are permanent.
6. **History**: every change, by whom, when (including `system` for automatic ones).

## 5. Find things (Incidents, Detections, Events)
- **Incidents:** filter by status and severity, or type an exact account name and press Enter. The filters stay in the address bar, so you can bookmark them.
- **Detections:**
  - filter by rule or by origin (Rules only / ML only);
  - open **Rule catalogue** at the bottom to see what every code means and its threshold.
- **Events:** the raw facts. Filter by account or event type (e.g. `auth.login.failed`).

## 6. Manage people and systems (Admin, admins only)
- **Users:**
  - add a user (lowercase username, password with 12+ characters, role);
  - **Make admin/analyst**;
  - **Deactivate**: they're locked out immediately, even mid-session.
  - You can't deactivate or demote yourself.
- **API keys:**
  - type a name (e.g. `web-app`), then **Create key**;
  - **copy the key at once**: it's never shown again;
  - give it to the system that sends events (see [integration.md](integration.md));
  - **Revoke** switches it off for good.

## 7. Explore the API by clicking (Swagger)
1. Open **http://127.0.0.1:8000/docs**.
2. Click **Authorize** (top right), enter username + password, then **Authorize**.
3. Open any endpoint, then **Try it out**, then **Execute**. You see the exact request (as a `curl` command) and the response.

## 8. Watch the system's health (with Docker)
- `docker compose --profile app --profile monitoring up -d --build`.
- **Grafana:** open http://localhost:3000 (user `admin`, password from your `.env`) → Dashboards → AEGIS. You get request rates, slow endpoints, errors, events per minute, detections and incidents, and rate-limit refusals.
- **Prometheus:** open http://localhost:9090 to query raw metrics, e.g. `aegis_detections_total`.

## 9. Self-protection demo
Log out, then try to log in 5 times with a wrong password for the same username. Log in as admin:
- **Incidents** shows a new incident for that username (AUTH-001, source `aegis`): AEGIS detected an attack on itself;
- more than 10 tries within 5 minutes are refused with "Too many requests".
