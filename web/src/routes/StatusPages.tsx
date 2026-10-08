// Manage public status pages: a slug, a title, and which monitors appear.

import { useState } from "react";

import { useDeleteStatusPage, useMonitors, useSaveStatusPage, useStatusPages } from "../lib/api";
import { confirmDelete } from "../lib/confirm";
import type { StatusPageConfig } from "../types";

type Draft = Omit<StatusPageConfig, "id"> & { id?: number };
const EMPTY: Draft = { slug: "", title: "", description: "", monitor_ids: [] };

export function StatusPages() {
  const pages = useStatusPages();
  const monitors = useMonitors();
  const save = useSaveStatusPage();
  const remove = useDeleteStatusPage();
  const [draft, setDraft] = useState<Draft | null>(null);

  const names = new Map(monitors.data?.map((m) => [m.id, m.name]));

  const toggle = (id: number) =>
    setDraft((d) =>
      d && {
        ...d,
        monitor_ids: d.monitor_ids.includes(id)
          ? d.monitor_ids.filter((x) => x !== id)
          : [...d.monitor_ids, id],
      },
    );

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!draft) return;
    save.mutate(
      { ...draft, description: draft.description || null },
      { onSuccess: () => setDraft(null) },
    );
  };

  return (
    <div className="page">
      <header className="page__head">
        <div>
          <h1>Status pages</h1>
          <p className="page__sub">
            Public pages anyone can open — names and up/down only, no URLs or errors.
          </p>
        </div>
        {!draft && (
          <button className="btn btn--primary" onClick={() => setDraft(EMPTY)}>
            + New status page
          </button>
        )}
      </header>

      {draft && (
        <form className="panel form" onSubmit={onSubmit}>
          <h2>{draft.id ? "Edit status page" : "New status page"}</h2>
          <div className="form__grid">
            <label>
              Title
              <input
                value={draft.title}
                onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                placeholder="manav.dev"
                required
              />
            </label>
            <label>
              Slug (URL)
              <input
                value={draft.slug}
                onChange={(e) =>
                  setDraft({ ...draft, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-") })
                }
                placeholder="my-services"
                pattern="[a-z0-9][a-z0-9-]{1,39}"
                required
              />
            </label>
          </div>
          <label>
            Message (optional — shown under the headline)
            <input
              value={draft.description ?? ""}
              onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              placeholder="Leave empty to generate one from current status"
            />
          </label>
          <div>
            <div className="form__legend">Monitors on this page</div>
            <div className="checklist">
              {monitors.data?.map((m) => (
                <label key={m.id} className="checklist__item">
                  <input
                    type="checkbox"
                    checked={draft.monitor_ids.includes(m.id)}
                    onChange={() => toggle(m.id)}
                  />
                  {m.name}
                </label>
              ))}
            </div>
          </div>
          {save.error && <p className="error">{save.error.message}</p>}
          <div className="form__actions">
            <button type="button" className="btn" onClick={() => setDraft(null)}>
              Cancel
            </button>
            <button className="btn btn--primary" disabled={save.isPending}>
              {draft.id ? "Save" : "Create"}
            </button>
          </div>
        </form>
      )}

      {pages.data?.length === 0 && !draft && (
        <section className="panel">
          <p className="muted">No status pages yet.</p>
        </section>
      )}

      {pages.data && pages.data.length > 0 && (
        <div className="incident-list">
          {pages.data.map((p) => (
            <div key={p.id} className="sp-admin-row">
              <div className="incident-row__main">
                <div className="row__name">{p.title}</div>
                <div className="row__url">
                  {p.monitor_ids.map((id) => names.get(id) ?? `#${id}`).join(", ") || "no monitors"}
                </div>
              </div>
              <a href={`/status/${p.slug}`} target="_blank" rel="noreferrer" className="mono">
                /status/{p.slug} ↗
              </a>
              <button className="btn btn--sm" onClick={() => setDraft({ ...p })}>
                Edit
              </button>
              <button
                className="btn btn--sm btn--danger"
                onClick={() => confirmDelete(p.title) && remove.mutate(p.id)}
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
