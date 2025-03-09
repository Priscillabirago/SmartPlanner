# Smart Study Planner - Preliminary Code

## Overview
This project is a **Smart Study Planner** designed for **Ghanaian students** to optimize their study schedules. The planner dynamically assigns study sessions based on **workload, priority, and availability** using a **greedy scheduling algorithm**. 

## Features
- **SQLite Database:** Stores user profiles, study subjects, and scheduled study sessions.
- **Dynamic Scheduling Algorithm:** Allocates study sessions based on priority and workload.
- **Automated Adjustments:** Ensures that high-priority subjects are scheduled first.
- **Basic Data Storage:** Tracks user study habits and completion rates.

## Project Structure
```
📁 study_planner_project/
│── 📄 study_planner.py        # Main script with database setup and scheduling algorithm
│── 📄 README.md               # Project documentation
│── 📄 requirements.txt        # Dependencies (if needed in future updates)
│── 📂 database/               # Directory for database files
│── 📂 docs/                   # Documentation and design notes
```

## Database Schema
The project uses **SQLite** with the following structure:
- **Users Table:** Stores user profiles (`id, name, study_hours_per_week, preferred_study_times`).
- **Subjects Table:** Stores subjects (`id, user_id, name, workload, priority`).
- **Study Sessions Table:** Tracks scheduled study sessions (`id, user_id, subject_id, start_time, end_time, completed`).

## Setup and Execution
### Prerequisites
- Python 3.x
- SQLite3 (included in Python)

### Running the Project
1. Clone the repository or copy the script.
2. Run the script to initialize the database and schedule study sessions:
   ```sh
   python study_planner.py
   ```
3. The generated study schedule will be displayed in the terminal, along with stored database records.

### Expected Output
The program will print a **generated study schedule** and **database contents** for verification. Example output:
```
Generated Study Schedule:
Subject: Mathematics | Start: 2024-03-08 10:00:00 | End: 2024-03-08 11:00:00
Subject: Science | Start: 2024-03-08 11:00:00 | End: 2024-03-08 12:00:00
...

Stored Users:
(1, 'John Doe', 10, 'Evenings')

Stored Subjects:
(1, 1, 'Mathematics', 4, 5)
(2, 1, 'History', 3, 3)
...
```

## Next Steps
- **Expand Scheduling Algorithm**: Add **rescheduling and adaptive learning**.
- **Frontend UI**: Develop a web or mobile interface for better usability.
- **Business & Branding Strategy**: Define adoption plans for schools and private tutors.
- **AI Integration (Stretch Goal)**: Explore machine learning models for study pattern predictions.


---
**Note:** This is a **preliminary version**, and further refinements will be added as development progresses.

