# 專案結構

## 目錄說明
reas/
├── app/: 主應用程式目錄
│   ├── __init__.py
│   ├── main.py
│   ├── core/: 核心配置和資料庫設定
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── database.py
│   ├── models/: 資料庫模型
│   │   ├── __init__.py
│   │   └── article.py
│   ├── schemas/: Pydantic 模型
│   │   ├── __init__.py
│   │   └── article.py
│   ├── api/: API 路由
│   │   ├── __init__.py
│   │   └── v1/
│   ├── services/: 業務邏輯層
│   │   ├── __init__.py
│   │   └── crawler/
│   └── static/: 靜態文件
└── tests/: 測試目錄
    └── __init__.py