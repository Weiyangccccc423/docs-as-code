# docs-as-code 工作流包

中文 | [English](README.md)

面向本地优先开发的可复用治理工作流：从一份产品文档开始，构建可追踪、可验证的 docs-as-code 项目仓库。

当前版本：**2.0.0**。版本源文件是 [`VERSION`](VERSION)，版本变更记录见 [`CHANGELOG.md`](CHANGELOG.md)。

## 提供能力

- 从空文件夹安全初始化项目仓库
- 归档、转换并结构化产品文档
- 设计系统架构、API、后端、数据模型、UI、前端和测试方案
- 通过权威 skill 路由、来源和完整性检查约束设计过程
- 自动检查运行环境，执行受审阅的环境修复
- 记录实现证据，进行本地验证和治理文档漂移控制
- 导出可验证的工作流包，并支持受保护的运行时刷新

## 工作流

| 阶段 | 工作内容 | 主要 skill |
| --- | --- | --- |
| 01 | 初始化空仓库 | `initializing-governance-repo` |
| 02 | 归档产品文档 | `archiving-product-document` |
| 03 | 结构化产品需求 | `structuring-product-requirements` |
| 04 | 推导并评审设计 | `designing-system-architecture` 及专业 skills |
| 05 | 验证文档结构并控制漂移 | `verifying-governance-docs` |
| 06 | 一次执行一个实现任务 | `executing-implementation-task` |

开始前请阅读 [`workflows/00-overview.md`](workflows/00-overview.md)。

## 快速开始

要求：Python 3.10+、Git 和 POSIX shell。只有 DOCX、HTML 或 PDF 产品文档才需要额外安装 `pandoc` 或 `pdftotext`。

在包含一份产品文档和已解包工作流包的新项目目录中运行：

```bash
./docs-as-code-workflow-pack/bin/governance-bootstrap --check --json
./docs-as-code-workflow-pack/bin/governance-bootstrap --json
```

手动使用源工作流包时：

```bash
bin/governance env --repair --check --target /path/to/new-project --json
bin/governance env --repair --target /path/to/new-project --json
bin/governance init --check --target /path/to/new-project --profile web-app --project-name "Project Name" --json
bin/governance init --target /path/to/new-project --profile web-app --project-name "Project Name" --json
bin/governance verify /path/to/new-project --check --json
bin/governance verify /path/to/new-project --json
bin/governance gate product-structuring /path/to/new-project --json
bin/governance status /path/to/new-project
```

`--check` 模式只读，不写入状态。执行写操作前，请检查返回结果中的 `argv`、阻塞项、skills 和后续动作。详细阶段流程和命令契约见 [`workflows/`](workflows/) 与 [`references/`](references/)。

## 本地验证

本地验证是权威门禁；GitHub Actions 仅在手动触发时运行。

```bash
make test
make verify-pack
```

发布前的完整检查见 [`references/release-readiness-checklist.md`](references/release-readiness-checklist.md)。

## 目录结构

```text
.
├── CHANGELOG.md # 版本变更和升级影响
├── bin/          # 命令包装器
├── scripts/      # 确定性检查和初始化脚本
├── skills/       # 工作流使用的 agent skills
├── references/   # 方法和实践参考
├── templates/    # 生成目标仓库文档的模板
├── tests/        # 工作流包测试
└── workflows/    # 分阶段操作流程
```

英文 README 中的 [Detailed package index and operational reference](README.md#detailed-package-index-and-operational-reference) 包含完整的模板、参考资料、skills 和高级运行说明。
