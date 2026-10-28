document.addEventListener("DOMContentLoaded", () => {
  // Search/filter rows on the admin dashboard.
  const search = document.getElementById("complaint-search");
  const table = document.getElementById("complaints-table");
  if (search && table) {
    search.addEventListener("input", () => {
      const query = search.value.toLowerCase().trim();
      table.querySelectorAll("tbody tr").forEach(row => {
        row.hidden = !row.textContent.toLowerCase().includes(query);
      });
    });
  }

  // Live complaint status updates on a student's tracking page.
  const trackingBox = document.getElementById("tracking-box");
  if (!trackingBox || typeof io === "undefined") return;

  const complaintId = trackingBox.dataset.complaintId;
  const statusElement = document.getElementById("live-status");
  const remarksElement = document.getElementById("live-remarks");
  const connectionElement = document.getElementById("connection-status");
  const timeline = document.getElementById("complaint-timeline");
  const progressFill = document.getElementById("progress-fill");
  const progressContainer = document.getElementById("status-progress");
  const progressMap = { "Submitted": 20, "Under Review": 40, "In Progress": 60, "Resolved": 80, "Closed": 100 };
  const progressOrder = ["Submitted", "Under Review", "In Progress", "Resolved", "Closed"];
  const socket = io();

  socket.on("connect", () => {
    connectionElement.textContent = "Connected — updates will appear automatically.";
    socket.emit("join_complaint", { complaint_id: complaintId });
  });

  socket.on("disconnect", () => {
    connectionElement.textContent = "Reconnecting to live updates…";
  });

  socket.on("complaint_updated", data => {
    if (data.complaint_id !== complaintId) return;

    statusElement.textContent = data.status;
    statusElement.className = "status status-" + data.status.toLowerCase().replaceAll(" ", "-");
    remarksElement.textContent = data.remarks || "No additional remarks.";

    if (progressFill) progressFill.style.width = (progressMap[data.status] || 20) + "%";
    if (progressContainer) {
      progressContainer.dataset.status = data.status;
      const steps = progressContainer.querySelectorAll(".progress-steps span");
      steps.forEach((step, index) => {
        step.classList.toggle("active", index <= progressOrder.indexOf(data.status));
      });
    }

    const item = document.createElement("article");
    item.className = "timeline-item";
    const dot = document.createElement("span");
    dot.className = "timeline-dot";
    const content = document.createElement("div");
    content.className = "timeline-content";
    const titleRow = document.createElement("div");
    titleRow.className = "timeline-title-row";
    const heading = document.createElement("h3");
    heading.textContent = data.status;
    const time = document.createElement("small");
    time.textContent = new Date(data.updated_at).toLocaleString();
    const remarks = document.createElement("p");
    remarks.textContent = data.remarks || "Status updated.";
    titleRow.append(heading, time);
    content.append(titleRow, remarks);
    item.append(dot, content);
    timeline.prepend(item);
  });
});
