import { useState, type FormEvent } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { ErrorBox, Loading, PageHeader } from "../components/ui";
import { timeAgo } from "../format";
import type { Role } from "../types";
import { useAsync } from "../useAsync";

export function AdminPage() {
  return (
    <>
      <PageHeader title="Admin" subtitle="People who can log in, and keys for systems that send events." />
      <div className="grid two">
        <Users />
        <ApiKeys />
      </div>
    </>
  );
}

function Users() {
  const { user: me } = useAuth();
  const users = useAsync(() => api.users(), []);
  const [form, setForm] = useState({ username: "", password: "", role: "analyst" as Role });
  const [error, setError] = useState<string | null>(null);

  async function act(action: () => Promise<unknown>) {
    setError(null);
    try {
      await action();
      users.reload();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function create(e: FormEvent) {
    e.preventDefault();
    act(async () => {
      await api.createUser(form);
      setForm({ username: "", password: "", role: "analyst" });
    });
  }

  return (
    <section className="card">
      <h2>Users</h2>
      {users.loading && !users.data && <Loading />}
      <table>
        <thead><tr><th>User</th><th>Role</th><th>Last login</th><th></th></tr></thead>
        <tbody>
          {users.data?.map((u) => (
            <tr key={u.id} className={u.is_active ? "" : "inactive"}>
              <td>{u.username}{!u.is_active && <span className="muted"> (deactivated)</span>}</td>
              <td>{u.role}</td>
              <td>{timeAgo(u.last_login_at)}</td>
              <td className="row">
                {u.id !== me?.id && (
                  <>
                    <button className="btn small" onClick={() => act(() => api.updateUser(u.id, { role: u.role === "admin" ? "analyst" : "admin" }))}>
                      Make {u.role === "admin" ? "analyst" : "admin"}
                    </button>
                    <button className="btn small" onClick={() => act(() => api.updateUser(u.id, { is_active: !u.is_active }))}>
                      {u.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <form className="stack space-top" onSubmit={create}>
        <h3>Add a user</h3>
        <input placeholder="username (lowercase)" value={form.username} required pattern="[a-z0-9._\-]{3,50}"
          onChange={(e) => setForm({ ...form, username: e.target.value })} aria-label="New username" />
        <input type="password" placeholder="password (12+ characters)" value={form.password} minLength={12} required
          onChange={(e) => setForm({ ...form, password: e.target.value })} aria-label="New password" autoComplete="new-password" />
        <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value as Role })} aria-label="Role">
          <option value="analyst">analyst</option>
          <option value="admin">admin</option>
        </select>
        <button className="btn primary">Create user</button>
      </form>
      {error && <ErrorBox message={error} />}
    </section>
  );
}

function ApiKeys() {
  const keys = useAsync(() => api.apiKeys(), []);
  const [name, setName] = useState("");
  const [newKey, setNewKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function create(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const created = await api.createApiKey(name);
      setNewKey(created.key);
      setName("");
      keys.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function revoke(id: string) {
    setError(null);
    try {
      await api.revokeApiKey(id);
      keys.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className="card">
      <h2>API keys</h2>
      <p className="muted small">Systems send events with the header <code>X-API-Key</code>. Keys can send events, nothing else.</p>
      {newKey && (
        <div className="notice" role="status">
          <strong>Copy this key now. It will never be shown again.</strong>
          <code className="secret">{newKey}</code>
          <button className="btn small" onClick={() => navigator.clipboard?.writeText(newKey)}>Copy</button>
          <button className="btn small" onClick={() => setNewKey(null)}>I've saved it</button>
        </div>
      )}
      <table>
        <thead><tr><th>Name</th><th>Prefix</th><th>Last used</th><th></th></tr></thead>
        <tbody>
          {keys.data?.map((k) => (
            <tr key={k.id} className={k.is_active ? "" : "inactive"}>
              <td>{k.name}</td>
              <td><code>{k.prefix}</code></td>
              <td>{timeAgo(k.last_used_at)}</td>
              <td>{k.is_active ? <button className="btn small" onClick={() => revoke(k.id)}>Revoke</button> : <span className="muted">revoked</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <form className="row space-top" onSubmit={create}>
        <input placeholder="Key name, e.g. web-app" value={name} onChange={(e) => setName(e.target.value)} required aria-label="Key name" />
        <button className="btn primary">Create key</button>
      </form>
      {error && <ErrorBox message={error} />}
    </section>
  );
}
