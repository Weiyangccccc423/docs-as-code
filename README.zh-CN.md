# docs-as-code 工作流包

中文 | [English](README.md)

可安装的本地优先治理工具：从一份产品文档开始，构建可追踪、可验证的 docs-as-code 项目仓库。

当前版本：**2.0.0**。版本源文件是 [`VERSION`](VERSION)，变更记录见 [`CHANGELOG.md`](CHANGELOG.md)。

## 安装

推荐使用 `uv` 安装到独立的工具环境：

```bash
uv tool install git+https://github.com/Weiyangccccc423/docs-as-code.git
```

安装后直接使用短命令 `dac`，不会污染项目自身的 Python 环境。`docs-as-code` 仍然作为兼容别名保留。如果当前环境没有 `uv`，可以使用带 pip 的 Python 3.10 及以上版本：

```bash
python3 -m pip install git+https://github.com/Weiyangccccc423/docs-as-code.git
```

如果不想安装 Python 包，也可以直接使用导出工作流包中的同一个短命令：

```text
my-project/
├── product.md
└── docs-as-code-workflow-pack/
```

```bash
cd my-project
./docs-as-code-workflow-pack/bin/dac --help
./docs-as-code-workflow-pack/bin/dac init --check
./docs-as-code-workflow-pack/bin/dac init
```

离线入口会检查 Python 3.10 及以上版本，把工作流包加入 `PYTHONPATH`，并把当前目录作为项目目标。`DOCS_AS_CODE_PYTHON` 可以指定其他兼容的 Python 解释器。

## 从一份产品文档开始

使用已安装 CLI 时，新项目根目录只需要放一份产品文档；工作流包由安装包提供，不需要复制或解压到项目中：

```text
my-project/
└── product.md
```

支持 `.md`、`.markdown`、`.txt`、`.docx`、`.pdf`、`.html` 和 `.htm`。DOCX/HTML 转换可能需要 `pandoc`，PDF 转换可能需要 `pdftotext`。

```bash
cd my-project
dac init
```

`dac init` 会检查工作流包和运行环境，自动发现 `product.md`，归档产品源文档，并生成标准治理仓库结构。如果根目录存在多份产品文档，请明确指定：

```bash
dac init /path/to/product.pdf
```

没有产品文档或发现多份产品文档时，命令会在写入任何项目文件之前停止。

## 常用命令

```bash
dac status
dac next
dac verify
dac doctor
dac --help
```

| 命令 | 用途 |
| --- | --- |
| `dac help` | 查看首次使用步骤和命令索引。 |
| `dac help COMMAND` | 查看某个命令的参数和示例，例如 `dac help init`。 |
| `dac status` | 查看当前项目和工作流阶段。 |
| `dac next` | 只读查看下一个有证据支持的工作流动作。 |
| `dac next --apply` | 执行一个经过校验的动作，然后刷新工作流证据。 |
| `dac verify --check` | 验证治理状态，不更新状态。 |
| `dac doctor` | 检查必需工具并给出安全修复建议。 |
| `dac upgrade --check` | 预览目标项目运行时升级。 |

`dac --help` 等同于 `dac help`，每个命令也支持 `dac COMMAND --help`。

在已初始化项目的任意子目录中运行 `dac status`、`dac next`、`dac verify`、`dac doctor` 或 `dac upgrade` 时，CLI 会自动向上定位最近的治理仓库根目录。显式指定其他目录时，`-C` 可以写在命令前后：`dac -C /path/to/project status` 与 `dac status -C /path/to/project` 等价。命令或参数错误会直接提示应运行的帮助命令；长选项不接受容易产生歧义的缩写。

初始化后的目标仓库也会生成短入口 `bin/dac`，无需再次安装 Python 包即可运行 `bin/dac status`、`bin/dac next`、`bin/dac verify --check`、`bin/dac doctor` 和 `bin/dac --help`。初始化和运行时升级仍需要可信的源工作流包或已安装的 `dac`，因此目标内的 `bin/dac init`、`bin/dac upgrade` 和 `bin/dac next --apply` 会明确停止并给出来源要求。

默认输出简短的人类可读摘要；Agent 和脚本使用 `--json` 获取完整证据与后续动作契约。

给 Agent 或脚本使用时，先用只读 JSON 模式检查，再执行写操作：

```bash
dac init --check --json
dac init --json
dac next --json
dac next --apply --json
dac verify --check --json
```

`dac next` 始终是只读的。人类可读输出会把路由标记为 `executable`、`manual input required`、`approval required`、`blocked` 或 `complete`；只有动作提供完整可执行 `argv` 契约时才会显示 `Run: dac next --apply`。人工动作会直接显示工作项、目标和主要文件，阻塞动作会显示有界原因与恢复路径。`dac next --apply` 才是显式写入路径；遇到快照过期、审批、命令结构异常、步骤失败或刷新失败时会停止。

初始化后，项目会包含自己的短入口 `bin/dac`、完整的 `bin/governance` 运行时、`docs/` 治理文档、`AGENTS.md` 和工作流包快照；即使从项目子目录调用，`bin/dac` 也始终绑定该项目根目录。阶段规则见 [`workflows/00-overview.md`](workflows/00-overview.md)。

## 目录结构

```text
.
├── docs_as_code/ # 可安装的 dac CLI
├── bin/          # 源工作流包命令包装器，包含短命令 dac
├── scripts/      # 确定性检查和初始化脚本
├── skills/       # Agent 使用的 skills
├── references/   # 方法和实践参考
├── templates/    # 目标仓库文档模板
├── tests/        # 工作流包测试
└── workflows/    # 分阶段操作流程
```

维护者使用 `make test` 和 `make verify-pack`；`make install-smoke-check` 只读检查打包环境，`make install-smoke` 会在临时目录中真实构建并安装 wheel。完整源包、制品和发布流程见英文 README 的折叠参考区，以及 [`references/release-readiness-checklist.md`](references/release-readiness-checklist.md)。
