# 🧠 NeuralEdge AI
## Explainable AI Powered Deepfake Detection & Digital Forensics Platform


![NeuralEdge AI](https://img.shields.io/badge/AI-Deepfake%20Detection-cyan)
![Framework](https://img.shields.io/badge/Framework-Next.js-black)
![UI](https://img.shields.io/badge/UI-TailwindCSS-blue)
![Status](https://img.shields.io/badge/Development-Frontend%20Phase-green)


---

# 📌 Project Overview

**NeuralEdge AI** is an explainable artificial intelligence platform designed for deepfake image detection and digital forensic analysis.

The platform transforms deep learning-based deepfake detection models into a user-friendly forensic investigation system.

Unlike traditional binary classifiers that only output:


Real / Fake


NeuralEdge AI provides:

- Prediction results
- Confidence scores
- Model information
- Explainable AI visualization
- Investigation management
- Forensic report generation


The system is designed to support investigators by providing transparent AI-based evidence analysis.


---

# 🎯 Main Objectives

NeuralEdge AI aims to:

- Detect manipulated deepfake images using deep learning
- Provide explainable predictions
- Visualize model decision regions
- Support forensic investigation workflows
- Generate structured investigation reports


---

# ✨ Current Frontend Features

## 1. Modern AI Landing Website

Implemented:

- NeuralEdge AI branding
- Cybersecurity inspired design
- Glassmorphism interface
- Responsive layout
- AI capability showcase


Sections:

- Hero section
- Feature cards
- Technology stack
- Platform introduction


---

# 2. User Authentication System

The platform supports two user types:


## Guest User

Guest users can:

- Access homepage
- Use quick deepfake detection
- View basic prediction results


Restrictions:

- No case management
- No saved reports
- No investigator dashboard access


---

## Investigator User

Investigators can access:

- Dashboard
- Evidence analysis
- Investigation cases
- Reports
- Model analytics
- Settings


---

# 3. Investigator Dashboard

The dashboard provides:

## Statistics

- Total analyses
- Fake detections
- Real images
- Generated reports


## AI System Monitoring

Displays:

- AI engine status
- Model information
- Explainability status


## Model Analytics

Supports:

- Ensemble Model
- MobileNetV2
- ResNet50V2
- Xception


Metrics:

- Accuracy
- ROC-AUC
- F1 Score


## Investigation Management

Includes:

- Current investigation
- Recent activity
- Quick actions


---

# 4. Evidence Analysis Interface

The Analyze page provides:


## Image Upload

Features:

- Drag and drop upload
- Image preview
- File validation
- Evidence submission interface


## AI Processing Pipeline


Workflow:

Image Upload
    ↓

Image Validation
    ↓

RGB Preprocessing
    ↓

Deep Learning Inference
    ↓

Grad-CAM Generation
    ↓

Forensic Report Preparation



---

# 5. Explainable AI Interface

NeuralEdge AI includes frontend support for:


## Detection Result

Displays:

- Prediction
- Confidence
- Threshold
- Model used


Example:
Prediction:
FAKE IMAGE
Confidence:
97.6%
Model:
Ensemble


---

## Grad-CAM Visualization

Prepared interface for:

- Original image
- Heatmap visualization
- AI decision explanation


Future support:

- SHAP
- LIME


---

# 6. Forensic Reports System

Implemented:

- Report dashboard
- Investigation report table
- Report preview
- PDF generation interface


Reports contain:

- Case ID
- Prediction
- Confidence
- Model information
- Explainability status


---

# 🏗️ Frontend Architecture

frontend/
│
├── src/
│
│   ├── app/
│   │
│   │   ├── page.tsx
│   │   ├── login/
│   │   ├── register/
│   │   ├── detect/
│   │   ├── dashboard/
│   │   ├── analyze/
│   │   ├── reports/
│   │   ├── cases/
│   │   ├── model-analytics/
│   │   └── settings/
│   │
│   │
│   ├── components/
│   │
│   │   ├── Navbar.tsx
│   │   ├── Sidebar.tsx
│   │   ├── StatsCard.tsx
│   │   ├── ModelComparison.tsx
│   │   ├── ReportPreview.tsx
│   │   └── Authentication Components
│   │
│   │
│   ├── services/
│   │
│   ├── hooks/
│   │
│   └── utils/
│
│
├── package.json
│
└── README.md


---

# 🛠️ Technology Stack


## Frontend

| Technology | Purpose |
|-|-|
| Next.js | React framework |
| TypeScript | Type safety |
| Tailwind CSS | UI styling |
| Framer Motion | Animations |
| Lucide React | Icons |
| React Context | Authentication state |


---

# 🚀 Installation Guide


## Requirements

Install:

- Node.js
- npm
- VS Code


Check:

```bash
node -v

npm -v

Install Dependencies
Navigate to frontend:
cd frontend

Install packages:
npm install

Run Development Server
npm run dev

Open:
http://localhost:3000

🔐 Authentication Flow
Current frontend authentication:
Guest User

      |
      |
Login

      |
      |
Investigator Session

      |
      |
Dashboard Access


Future backend authentication:
Frontend

↓

FastAPI Authentication API

↓

JWT Token

↓

PostgreSQL User Database

🤖 Future Backend Integration
The frontend is prepared for integration with:
Backend
FastAPI
Machine Learning
TensorFlow/Keras
Models:
- MobileNetV2
- ResNet50V2
- Xception
- Ensemble Model
🔄 Final System Architecture

User

 |

Next.js Frontend

 |

FastAPI Backend

 |

Deep Learning Inference Engine

 |

TensorFlow Models

 |

Database

 |

Report Storage
📅 Future Development Roadmap
Phase 1 — Frontend Completion
- Complete authentication
- Guest detection workflow
- Protected routes
- UI polishing
Phase 2 — Backend Development
Implement:
- FastAPI server
- Authentication API
- Image upload API
- Detection API
- Report API
Phase 3 — Model Integration
Connect:
- Trained deep learning models
- Ensemble inference
- Confidence calculation
- Explainability generation
Phase 4 — Database Integration
Implement:
- Users
- Cases
- Analyses
- Reports
Phase 5 — Deployment
Deploy:
- Frontend
- Backend
- AI inference service
- Database
📌 Final Goal
NeuralEdge AI will become a complete explainable deepfake detection platform capable of:
✅ Detecting manipulated images
✅ Explaining AI decisions
✅ Managing forensic investigations
✅ Generating evidence reports
✅ Supporting professional investigation workflows

👨‍💻 Development Status
Current Status:
Frontend Development Phase

████████░░ 80%


Completed:
✅ UI Architecture
✅ Dashboard
✅ Analysis Workflow
✅ Authentication Foundation
✅ Reports Interface  
Next:
- Backend integration
- Real model connection
- Database implementation
- Deployment
License
Academic FYDP Project
NeuralEdge AI © 2026

This README is structured so that when you later create the backend repository, you can extend it instead of rewriting it.