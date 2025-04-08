/**
 * Ghana Smart Study Planner - Main JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.forEach(function(tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.forEach(function(popoverTriggerEl) {
        new bootstrap.Popover(popoverTriggerEl);
    });

    // Mark study session as completed via AJAX
    const completeSessionBtns = document.querySelectorAll('.complete-session-btn');
    if (completeSessionBtns.length > 0) {
        completeSessionBtns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                const sessionId = this.getAttribute('data-session-id');
                
                fetch(`/mark_completed/${sessionId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Update UI to show completion
                        const sessionEl = document.querySelector(`.study-session[data-session-id="${sessionId}"]`);
                        if (sessionEl) {
                            sessionEl.classList.add('completed');
                            this.disabled = true;
                            this.innerHTML = '<i class="fas fa-check"></i> Completed';
                        }
                    }
                })
                .catch(error => console.error('Error:', error));
            });
        });
    }

    // Mark task as completed via AJAX
    const completeTaskBtns = document.querySelectorAll('.complete-task-btn');
    if (completeTaskBtns.length > 0) {
        completeTaskBtns.forEach(function(btn) {
            btn.addEventListener('click', function() {
                const taskId = this.getAttribute('data-task-id');
                
                fetch(`/subjects/task/complete/${taskId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Update UI to show completion
                        const taskEl = document.querySelector(`.task-item[data-task-id="${taskId}"]`);
                        if (taskEl) {
                            taskEl.classList.add('completed');
                            this.disabled = true;
                            this.innerHTML = '<i class="fas fa-check"></i> Completed';
                        }
                    }
                })
                .catch(error => console.error('Error:', error));
            });
        });
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
            events: window.calendarEvents || [], // Get events from the page
            eventTimeFormat: {
                hour: '2-digit',
                minute: '2-digit',
                meridiem: true
            },
            eventClick: function(info) {
                // Handle event click (redirect to session details)
                window.location.href = `/scheduler/session/${info.event.id}`;
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
    if (subjectChartEl && window.subjectData) {
        const ctx = subjectChartEl.getContext('2d');
        
        const labels = Object.keys(window.subjectData);
        const data = labels.map(subject => window.subjectData[subject].hours);
        const backgroundColor = labels.map(subject => window.subjectData[subject].color);
        
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
    if (completionChartEl && typeof window.completionRate !== 'undefined') {
        const ctx = completionChartEl.getContext('2d');
        
        new Chart(ctx, {
            type: 'gauge',
            data: {
                datasets: [{
                    value: window.completionRate,
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