# 法规对比系统

一个智能化的法规对比工具，支持多层级标题对比、AI智能总结，用于分析新老法规的差异。

## 功能特点

- **多层级对比**：支持章、条、款、目四个层级的对比
- **智能匹配算法**：三轮匹配策略（编号精确匹配 → 相似度匹配 → 新增/删除判定）
- **AI智能总结**：使用大模型自动生成变更总结
- **多格式报告**：生成JSON、详细报告、简洁总结三种格式

## 项目结构

```
regulation-comparison/
├── backend/
│   ├── chinoapi.py           # AI API调用模块
│   ├── extract_regulation.py # 法规提取模块
│   ├── regulation_comparator.py # 核心对比模块
│   └── text/                 # 法规数据目录
│       ├── 2016.json         # 老法规数据
│       ├── 2025.json         # 新法规数据
│       └── comparison_*.txt  # 对比报告输出
├── docs/
│   └── 校对流程说明.md        # 详细流程文档
└── README.md
```

## 快速开始

### 1. 环境配置

```bash
# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install requests python-dotenv
```

### 2. 配置API密钥

创建 `backend/.env` 文件：

```
LLM_URL=https://app.chino-ai.com/api/oai/v1/chat/completions
LLM_TOKEN=your_api_token_here
LLM_MODEL=glm-5
```

### 3. 运行程序

```bash
source venv/bin/activate
python backend/regulation_comparator.py
```

## 对比流程

### 层级说明

| 层级 | 编号格式 | 说明 |
|------|---------|------|
| 一级标题 | 第一章、第二章... | 章/章节 |
| 二级标题 | 第一条、第二条... | 条/条款 |
| 三级标题 | （一）、（二）... | 款/款项 |
| 四级标题 | 1.、2.、1、2、... | 目/项目 |

### 对比策略

| 层级 | 对比内容 |
|------|---------|
| 一级标题 | 仅对比 title |
| 二级标题 | 仅对比 title |
| 三级标题 | 对比 title 和 content |
| 四级标题 | 对比 title 和 content |

### 三轮匹配算法

1. **编号精确匹配**：按编号（如"第一条"）精确配对
2. **相似度匹配**：对未匹配项计算title相似度（≥50%判定为修改/移动）
3. **新增/删除判定**：剩余未匹配项判定为新增或删除

## 输出报告

| 文件 | 说明 |
|------|------|
| comparison_result.json | 结构化JSON数据 |
| comparison_report.txt | 详细对比报告（含AI总结） |
| comparison_summary.txt | 简洁变更总结 |

## 示例结果

```
对比摘要：
  新增项目: 3
  删除项目: 1
  修改项目: 19
  未变化项目: 46
```

## 详细文档

请参阅 [docs/校对流程说明.md](docs/校对流程说明.md) 获取完整的流程说明。

## License

MIT
