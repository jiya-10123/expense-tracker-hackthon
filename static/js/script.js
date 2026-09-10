/* ------------------------------------------------------------------
   Expense Tracker - Custom JavaScript
   Handles: Chart.js dashboard charts + delete confirmation modal
   ------------------------------------------------------------------ */

// A consistent color palette used across charts and category badges
const CATEGORY_COLORS = {
    "Food": "#f59e0b",
    "Transport": "#3b82f6",
    "Shopping": "#ec4899",
    "Education": "#10b981",
    "Entertainment": "#8b5cf6",
    "Bills": "#ef4444",
    "Other": "#6b7280",
};

function colorForLabel(label) {
    return CATEGORY_COLORS[label] || "#9ca3af";
}

/**
 * Fetches chart data from the Flask API endpoints and renders
 * the category doughnut chart + monthly bar chart on the dashboard.
 * Called from dashboard.html only when there is data to show.
 */
function initDashboardCharts() {
    // ---------- Category Doughnut Chart ----------
    fetch("/api/category-data")
        .then((response) => response.json())
        .then((data) => {
            const ctx = document.getElementById("categoryChart");
            if (!ctx) return;

            new Chart(ctx, {
                type: "doughnut",
                data: {
                    labels: data.labels,
                    datasets: [{
                        data: data.values,
                        backgroundColor: data.labels.map(colorForLabel),
                        borderWidth: 2,
                        borderColor: "#ffffff",
                    }],
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { position: "bottom" },
                        tooltip: {
                            callbacks: {
                                label: function (context) {
                                    return `${context.label}: ₹${context.parsed.toFixed(2)}`;
                                },
                            },
                        },
                    },
                },
            });
        })
        .catch((err) => console.error("Failed to load category chart data:", err));

    // ---------- Monthly Bar Chart ----------
    fetch("/api/monthly-data")
        .then((response) => response.json())
        .then((data) => {
            const ctx = document.getElementById("monthlyChart");
            if (!ctx) return;

            new Chart(ctx, {
                type: "bar",
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: "Total Spending",
                        data: data.values,
                        backgroundColor: "#4f46e5",
                        borderRadius: 6,
                        maxBarThickness: 48,
                    }],
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: function (context) {
                                    return `₹${context.parsed.y.toFixed(2)}`;
                                },
                            },
                        },
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                callback: function (value) {
                                    return "₹" + value;
                                },
                            },
                        },
                    },
                },
            });
        })
        .catch((err) => console.error("Failed to load monthly chart data:", err));
}

/**
 * Wires up the delete-confirmation modal on the Transactions page.
 * When a delete button is clicked, this reads the expense info from
 * its data-* attributes and points the modal's form at the right URL.
 */
document.addEventListener("DOMContentLoaded", function () {
    const deleteModal = document.getElementById("deleteModal");
    if (!deleteModal) return;

    deleteModal.addEventListener("show.bs.modal", function (event) {
        const button = event.relatedTarget;
        const deleteUrl = button.getAttribute("data-delete-url");
        const description = button.getAttribute("data-expense-desc");

        const form = document.getElementById("deleteForm");
        const descLabel = document.getElementById("deleteExpenseDesc");

        form.setAttribute("action", deleteUrl);
        descLabel.textContent = '"' + description + '"';
    });
});
