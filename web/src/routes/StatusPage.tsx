// The public status page. v3.
//
// This is a DIFFERENT PRODUCT that happens to share a database. The app is
// dense and for you; this page is for someone who wants one answer and it
// should be almost empty.
//
// Do not import MonitorRow, Sparkline, or anything else from ../components
// here. The moment you reuse the dashboard's atoms you inherit the dashboard's
// density, and you will end up showing a stranger your p99 latency when all
// they wanted to know was whether it is your fault or their wifi.
//
// It also renders with no nav and no auth -- note the route in App.tsx sits
// outside the app shell for exactly that reason.

export function StatusPage() {
  return (
    <div className="status-page">
      <h1>Status page</h1>
      <p>
        v3. Build <code>public_status</code> in{" "}
        <code>api/app/routers/status.py</code> first — the notes in that file
        cover the slug question and the 90-day rollup.
      </p>
      <ul>
        <li>Big banner: “All systems operational”, and nothing else above the fold.</li>
        <li>Service list with 90-day uptime bar strips underneath.</li>
        <li>Recent incidents below, plain prose, no jargon.</li>
      </ul>
    </div>
  );
}
