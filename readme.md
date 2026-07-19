# RecallDSA

A smart Data Structures and Algorithms revision platform that helps students retain problem-solving patterns through spaced repetition and personalized weekly assessments.

![Status](https://img.shields.io/badge/status-in%20development-yellow)
![Backend](https://img.shields.io/badge/backend-Django%20%7C%20DRF-092E20)
![Frontend](https://img.shields.io/badge/frontend-React-61DAFB)
![Database](https://img.shields.io/badge/database-PostgreSQL-336791)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Overview

RecallDSA addresses a critical gap in the DSA learning process: **retention**. Most existing platforms focus on problem-solving volume, but fail to help learners retain the underlying patterns over time. This platform is designed to bridge that gap by combining spaced repetition, weak-topic analysis, and periodic assessments into a single, focused learning experience.

---

## Problem Statement

Despite solving hundreds of DSA problems, most students face the same challenges:

- Forgetting solutions and approaches within weeks of solving them
- Lack of a structured revision cycle for previously solved problems
- No visibility into weak topics or recurring pattern gaps
- Inability to test retention on problems they have already solved

Existing platforms provide problems and solutions, but none provide a systematic revision framework tailored to individual learning progress.

---

## Solution

RecallDSA introduces a structured retention system built around four core principles:

1. **Spaced Repetition** — Automatically schedules problem revisions based on user performance and time decay.
2. **Pattern-Based Learning** — Categorizes every problem by DSA pattern (Sliding Window, Two Pointers, Dynamic Programming, etc.) for focused practice.
3. **Weekly Assessments** — Generates timed tests every weekend based on problems solved during the week.
4. **Weak-Topic Analysis** — Identifies patterns where the user struggles and prioritizes them in future revisions.

---

## Key Features

### Core Features
- User authentication and profile management
- Problem tracking with pattern-based tagging
- Personalized daily revision queue
- Spaced repetition scheduling engine
- Weekly timed assessments
- Progress dashboard with performance analytics
- Weak-topic identification and recommendations

### Planned Features
- LeetCode integration for automatic problem import
- Peer skill matching for collaborative practice
- AI-powered hint system using LLMs
- Mobile-responsive Progressive Web App (PWA)

---

## Technology Stack

### Backend
- **Framework:** Django, Django REST Framework
- **Database:** PostgreSQL
- **Authentication:** JSON Web Tokens (JWT)
- **Language:** Python 3.10+

### Frontend
- **Library:** React 18
- **Routing:** React Router
- **Styling:** Tailwind CSS
- **State Management:** Context API
- **Data Visualization:** Recharts

### Infrastructure
- **Version Control:** Git and GitHub
- **Frontend Deployment:** Vercel
- **Backend Deployment:** Railway
- **Database Hosting:** Railway PostgreSQL

---

## System Architecture

```
+------------------+        +----------------------+        +------------------+
|                  |        |                      |        |                  |
|   React Client   | <----> |   Django REST API    | <----> |   PostgreSQL     |
|                  |  HTTPS |                      |   ORM  |                  |
+------------------+        +----------------------+        +------------------+
                                       |
                                       v
                            +----------------------+
                            |   Revision Engine    |
                            |   (Modified SM-2)    |
                            +----------------------+
```

---

## Project Structure

```
recall-dsa/
├── backend/
│   ├── recalldsa/           # Main Django project configuration
│   ├── users/               # Authentication and user management
│   ├── problems/            # Problem catalog and pattern tagging
│   ├── revisions/           # Spaced repetition scheduling logic
│   ├── assessments/         # Weekly assessment generation
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/      # Reusable UI components
│   │   ├── pages/           # Route-based page components
│   │   ├── services/        # API integration layer
│   │   └── utils/           # Helper functions
│   └── package.json
│
├── docs/                    # Technical documentation
└── README.md
```

---

## Spaced Repetition Algorithm

RecallDSA uses a modified version of the SuperMemo 2 (SM-2) algorithm, adapted for programming problems:

1. When a user solves a problem, they rate their confidence on a scale of 1 to 5.
2. The system calculates the next revision interval based on:
   - Current confidence rating
   - Problem difficulty (Easy, Medium, Hard)
   - Previous revision performance
3. Revision intervals follow an exponential pattern:
   - Poor performance: 1 to 2 days
   - Moderate performance: 3 to 7 days
   - Strong performance: 14 to 30 days
4. All problems due for revision are aggregated into a weekly assessment every Saturday.

This approach mirrors cognitive science research on long-term memory formation.

---

## Development Roadmap

### Phase 1: Foundation
- [x] Repository setup and project initialization
- [ ] Database schema design and migrations
- [ ] JWT-based authentication system
- [ ] Base REST API structure

### Phase 2: Core Functionality
- [ ] Problem CRUD operations
- [ ] Pattern tagging system
- [ ] Spaced repetition engine
- [ ] Daily revision dashboard

### Phase 3: Advanced Features
- [ ] Weak-topic analysis engine
- [ ] Progress analytics and visualization
- [ ] Weekly assessment module
- [ ] Personalized recommendations

### Phase 4: Enhancements
- [ ] LeetCode API integration
- [ ] Peer matching algorithm
- [ ] AI-powered hint system
- [ ] Mobile responsiveness

### Phase 5: Deployment
- [ ] Backend deployment on Railway
- [ ] Frontend deployment on Vercel
- [ ] Custom domain configuration
- [ ] CI/CD pipeline setup

---

## Target Users

- Computer Science students preparing for technical interviews
- Self-taught developers learning Data Structures and Algorithms
- Working professionals maintaining their problem-solving skills
- Candidates targeting FAANG and product-based companies

---

## Current Status

This project is in active development. Features are being built incrementally with regular commits. Detailed progress can be tracked through the repository's commit history and project board.

---

## Getting Started

Setup instructions and installation guides will be added as the project reaches its Minimum Viable Product (MVP) stage.

### Prerequisites (Planned)
- Python 3.10 or higher
- Node.js 18 or higher
- PostgreSQL 14 or higher
- Git

---

## Motivation

This project originated from a personal challenge. As a computer science student solving multiple LeetCode problems daily, I observed that consistency in solving did not translate to long-term retention. Solutions faded within weeks, and existing tools did not address this gap systematically.

RecallDSA is being built to solve this problem, not just for me, but for every learner who has felt the frustration of forgetting what they once solved.

---

## Contributing

This project is currently maintained as a solo build. Contributions, feature suggestions, and issue reports will be welcomed once the core MVP is stable.

---

## Contact

**Saurabh Kumar**  
- GitHub: [github.com/Skwork75](https://github.com/Skwork75)
- LinkedIn: [linkedin.com/in/saurabh-kumar](https://linkedin.com/in/saurabh-kumar)
- LeetCode: [leetcode.com/Saurab_h_Singh](https://leetcode.com/Saurab_h_Singh)

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for full details.

---

**Built and maintained by Saurabh Kumar.**