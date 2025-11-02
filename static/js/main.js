/**
 * Smart Study Planner - Main JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = Array.from(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    for (const tooltipTriggerEl of tooltipTriggerList) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    }

    // Initialize popovers
    const popoverTriggerList = Array.from(document.querySelectorAll('[data-bs-toggle="popover"]'));
    for (const popoverTriggerEl of popoverTriggerList) {
        new bootstrap.Popover(popoverTriggerEl);
    }

    // Mark study session as completed via AJAX
    const completeSessionBtns = document.querySelectorAll('.complete-session-btn');
    if (completeSessionBtns.length > 0) {
        for (const btn of completeSessionBtns) {
            btn.addEventListener('click', function(event) {
                const button = event.currentTarget;
                const sessionId = button.dataset.sessionId;
                const originalHtml = button.innerHTML;

                button.disabled = true;
                button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Marking...';

                fetch(`/mark_completed/${sessionId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({})
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`Request failed with status ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        // Update UI to show completion
                        const sessionEl = document.querySelector(`.study-session[data-session-id="${sessionId}"]`);
                        if (sessionEl) {
                            sessionEl.classList.add('completed');
                        }
                        button.innerHTML = '<i class="fas fa-check"></i> Completed';
                    } else {
                        throw new Error(data.message || 'Unknown error');
                    }
                })
                .catch(error => {
                    console.error('Error completing session:', error);
                    button.disabled = false;
                    button.innerHTML = originalHtml;
                    alert('Unable to mark session as completed. Please try again or open the session details page.');
                });
            });
        }
    }

    // Mark task as completed via AJAX
    const completeTaskBtns = document.querySelectorAll('.complete-task-btn');
    if (completeTaskBtns.length > 0) {
        for (const btn of completeTaskBtns) {
            btn.addEventListener('click', function(event) {
                const button = event.currentTarget;
                const taskId = button.dataset.taskId;
                const originalHtml = button.innerHTML;

                button.disabled = true;
                button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Marking...';
                
                fetch(`/subjects/task/complete/${taskId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({})
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`Request failed with status ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        // Update UI to show completion
                        const taskEl = document.querySelector(`.task-item[data-task-id="${taskId}"]`);
                        if (taskEl) {
                            taskEl.classList.add('completed');
                        }
                        button.innerHTML = '<i class="fas fa-check"></i> Completed';
                    } else {
                        throw new Error(data.message || 'Unknown error');
                    }
                })
                .catch(error => {
                    console.error('Error completing task:', error);
                    button.disabled = false;
                    button.innerHTML = originalHtml;
                    alert('Unable to mark task as completed. Please try again or update it manually.');
                });
            });
        }
    }

    // Initialize FullCalendar if the element exists
    const calendarEl = document.getElementById('calendar');
    if (calendarEl) {
        const calendar = new FullCalendar.Calendar(calendarEl, {
            initialView: 'timeGridWeek',
            headerToolbar: {
                left: 'prev,next today',
                center: 'title',
                right: 'dayGridMonth,timeGridWeek,timeGridDay'
            },
            events: globalThis.calendarEvents || [], // Get events from the page
            eventTimeFormat: {
                hour: '2-digit',
                minute: '2-digit',
                meridiem: true
            },
            eventClick: function(info) {
                // Handle event click (redirect to session details)
                globalThis.location.href = `/scheduler/session/${info.event.id}`;
            },
            eventClassNames: function(arg) {
                // Add class to completed events
                if (arg.event.extendedProps.completed) {
                    return ['completed'];
                }
                return [];
            }
        });
        calendar.render();
    }

    // Initialize charts if they exist
    initializeCharts();
});

/**
 * Initialize Chart.js charts
 */
function initializeCharts() {
    // Subject distribution chart
    const subjectChartEl = document.getElementById('subjectDistributionChart');
    if (subjectChartEl && globalThis.subjectData) {
        const ctx = subjectChartEl.getContext('2d');
        
        const labels = Object.keys(globalThis.subjectData);
        const data = labels.map(subject => globalThis.subjectData[subject].hours);
        const backgroundColor = labels.map(subject => globalThis.subjectData[subject].color);
        
        new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: backgroundColor,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    },
                    title: {
                        display: true,
                        text: 'Study Hours by Subject'
                    }
                }
            }
        });
    }

    // Completion rate chart
    const completionChartEl = document.getElementById('completionRateChart');
    if (completionChartEl && globalThis.completionRate !== undefined) {
        const ctx = completionChartEl.getContext('2d');
        
        new Chart(ctx, {
            type: 'gauge',
            data: {
                datasets: [{
                    value: globalThis.completionRate,
                    data: [25, 50, 75, 100],
                    backgroundColor: ['#f44336', '#ff9800', '#4caf50', '#2196f3'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                title: {
                    display: true,
                    text: 'Session Completion Rate'
                },
                needle: {
                    radiusPercentage: 2,
                    widthPercentage: 3.2,
                    lengthPercentage: 80,
                    color: 'rgba(0, 0, 0, 1)'
                },
                valueLabel: {
                    display: true,
                    formatter: function(value) {
                        return value + '%';
                    },
                    color: 'rgba(0, 0, 0, 1)',
                    backgroundColor: 'rgba(0, 0, 0, 0)',
                    borderRadius: 5,
                    padding: {
                        top: 10,
                        bottom: 10
                    }
                }
            }
        });
    }
} 