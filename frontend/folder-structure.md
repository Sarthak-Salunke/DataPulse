# Frontend Folder Structure

This document outlines the folder structure of the frontend application.

```
frontend/
├── .gitignore
├── eslint.config.js
├── index.html
├── package-lock.json
├── package.json
├── postcss.config.js
├── README.md
├── tailwind.config.js
├── tsconfig.app.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── public/
│   └── vite.svg
└── src/
    ├── App.css
    ├── App.tsx
    ├── index.css
    ├── main.tsx
    ├── assets/
    │   └── react.svg
    ├── components/
    │   ├── InquiriesOverview.tsx
    │   ├── LandingPage.tsx
    │   ├── ProblemSection.tsx
    │   ├── SolutionSection.tsx
    │   ├── VerifiableComputeSection.tsx
    │   ├── Charts/
    │   │   ├── CreditDebitChart.tsx
    │   │   ├── PopularCountriesMap.tsx
    │   │   ├── SystemAdvicesChart.tsx
    │   │   └── TransactionChart.tsx
    │   ├── Common/
    │   │   ├── Header.tsx
    │   │   └── Sidebar.tsx
    │   ├── Dashboard/
    │   │   ├── Dashboard.tsx
    │   │   ├── MetricsCard.tsx
    │   │   └── RealTimeFeed.tsx
    │   ├── Modals/
    │   └── Pipeline/
    │       └── ArchitectureDiagram.tsx
    ├── hooks/
    ├── services/
    │   └── api.ts
    ├── styles/
    │   ├── animations.css
    │   └── theme.css
    ├── types/
    │   └── index.ts
    └── utils/
        └── constants.tsx
