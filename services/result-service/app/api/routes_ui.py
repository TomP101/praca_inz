from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Tasks Dashboard</title>
  <style>
    body {
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0;
      background: #0f172a;
      color: #e5e7eb;
    }
    header {
      padding: 16px 24px;
      background: #020617;
      border-bottom: 1px solid #1e293b;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    header h1 {
      font-size: 20px;
      margin: 0;
    }
    header span {
      font-size: 12px;
      color: #9ca3af;
    }
    main {
      padding: 24px;
      max-width: 960px;
      margin: 0 auto;
    }
    .cards {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .card {
      background: #020617;
      border-radius: 12px;
      padding: 16px;
      border: 1px solid #1e293b;
    }
    .card h2 {
      font-size: 13px;
      margin: 0 0 8px 0;
      color: #9ca3af;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    .card .value {
      font-size: 24px;
      font-weight: 600;
    }
    .card .sub {
      font-size: 12px;
      color: #6b7280;
      margin-top: 4px;
    }
    h3 {
      margin: 16px 0 8px 0;
      font-size: 15px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      background: #020617;
      border-radius: 12px;
      overflow: hidden;
      border: 1px solid #1e293b;
    }
    th, td {
      padding: 8px 12px;
      font-size: 13px;
      text-align: left;
    }
    th {
      color: #9ca3af;
      border-bottom: 1px solid #1e293b;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      font-size: 11px;
    }
    tr + tr td {
      border-top: 1px solid #111827;
    }
    #updatedAt {
      font-size: 12px;
      color: #6b7280;
      margin-bottom: 16px;
    }
    .pill-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .pill {
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 11px;
      border: 1px solid #1e293b;
      background: #020617;
    }
    .pill span {
      color: #9ca3af;
      margin-right: 4px;
    }
    button {
      padding: 6px 12px;
      border-radius: 999px;
      border: 1px solid #1e293b;
      background: #020617;
      color: #e5e7eb;
      font-size: 12px;
      cursor: pointer;
    }
    button:hover {
      background: #111827;
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Tasks Dashboard</h1>
      <span>Live metrics from result-service</span>
    </div>
    <div style="display:flex; gap:10px;">
      <button id="refreshBtn">Refresh now</button>
      <button id="truncateBtn">Truncate DB</button>
    </div>
  </header>

  <main>
    <div id="updatedAt">Loading...</div>

    <div class="cards">
      <div class="card">
        <h2>Total tasks</h2>
        <div class="value" id="totalTasks">–</div>
      </div>
      <div class="card">
        <h2>Throughput</h2>
        <div class="value" id="throughput">–</div>
        <div class="sub">tasks/minute</div>
      </div>
      <div class="card">
        <h2>Avg wait time</h2>
        <div class="value" id="avgWait">–</div>
        <div class="sub">created → started</div>
      </div>
    </div>

    <h3>Status counts</h3>
    <div class="card">
      <div class="pill-row" id="statusCounts"></div>
    </div>

    <h3>Avg run time by type</h3>
    <table>
      <thead>
        <tr>
          <th>Type</th>
          <th>Avg run time [s]</th>
        </tr>
      </thead>
      <tbody id="runTimesBody"></tbody>
    </table>
  </main>

  <script>
    function formatNumber(x, digits = 2) {
      if (x === null || x === undefined) return "–";
      return Number(x).toFixed(digits);
    }

    async function fetchStats() {
      try {
        const res = await fetch("/stats/summary");
        if (!res.ok) throw new Error(res.status);
        const data = await res.json();
        renderStats(data);
      } catch (e) {
        document.getElementById("updatedAt").textContent = "Error fetching stats";
      }
    }

    function renderStats(data) {
      document.getElementById("updatedAt").textContent =
        "Last update: " + new Date().toLocaleTimeString();

      document.getElementById("totalTasks").textContent = data.total_tasks ?? 0;
      document.getElementById("throughput").textContent =
        formatNumber(data.throughput_tasks_per_min);
      document.getElementById("avgWait").textContent =
        formatNumber(data.avg_wait_time_sec);

      const statusContainer = document.getElementById("statusCounts");
      statusContainer.innerHTML = "";
      for (const [k, v] of Object.entries(data.status_counts || {})) {
        const pill = document.createElement("div");
        pill.className = "pill";
        pill.innerHTML = "<span>" + k + "</span><strong>" + v + "</strong>";
        statusContainer.appendChild(pill);
      }

      const body = document.getElementById("runTimesBody");
      body.innerHTML = "";
      const order = ["CPU_INTENSIVE", "MEMORY_INTENSIVE"];
      for (const t of order) {
        if (!(t in (data.avg_run_time_sec_by_type || {}))) continue;
        const tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" + t + "</td><td>" +
          formatNumber(data.avg_run_time_sec_by_type[t]) +
          "</td>";
        body.appendChild(tr);
      }
    }

    document.getElementById("refreshBtn").addEventListener("click", fetchStats);

    document.getElementById("truncateBtn").addEventListener("click", async () => {
      if (!confirm("This will DELETE ALL tasks from DB. Continue?")) return;
      const res = await fetch("/admin/truncate", { method: "POST" });
      if (!res.ok) {
        alert("Truncate failed");
        return;
      }
      fetchStats();
    });

    fetchStats();
    setInterval(fetchStats, 5000);
  </script>
</body>
</html>
    """
