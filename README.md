# 马年朋友圈祝福贺卡生成器（前后端分离增强版）

本项目将原本在 Coze 中搭建的「上传朋友圈截图 + 选择/输入与对方关系 → 生成新年祝福语与贺卡」工作流，落地为一个前后端分离的网页应用。

- 前端：`newyear-card` · React + Vite + TypeScript + Tailwind + shadcn/ui
- 后端：`backend` · FastAPI · Provider 抽象（LLM / Vision / T2I / Storage）

默认在 **无密钥（Mock）模式** 下即可完整跑通体验；接入真实服务后无需修改前端或接口契约。

---

## 1. 目录结构

```bash
.
├── backend           # FastAPI 后端
│   ├── main.py       # API 入口与编排 /api/*
│   ├── providers/    # 可插拔 Provider 抽象（llm / vision / t2i / storage）
│   ├── data/         # 关系映射、祝福语模板、风格规则
│   ├── static/       # 上传图片与 mock 贺卡图片（通过 /static 暴露）
│   ├── requirements.txt
│   └── .env.example
└── newyear-card      # 前端应用
    ├── src/App.tsx   # 主页面结构与交互逻辑
    ├── src/components/ui/*
    ├── index.html
    ├── package.json
    └── .env.example
```

---

## 2. 后端：FastAPI 服务

### 2.1 环境准备

```bash
cd backend
# 建议使用内置 venv
source venv/bin/activate      # Windows 使用 venv\\Scripts\\activate
pip install -r requirements.txt
```

### 2.2 环境变量配置

复制示例文件并按需修改：

```bash
cp .env.example .env
```

`.env.example` 关键字段说明：

- `CORS_ALLOW_ORIGINS`：允许的前端地址（默认 `http://localhost:5173`）。
- `LLM_PROVIDER` / `LLM_API_KEY`：大模型 Provider（`mock` / `doubao` / `openai` 等自定义标识）。
- `VISION_PROVIDER` / `VISION_API_KEY`：视觉理解 / OCR Provider。
- `T2I_PROVIDER` / `T2I_API_KEY`：文生图 Provider。
- `STORAGE_PROVIDER` / `STORAGE_API_KEY`：对象存储 Provider。

> 注意：当前代码中 **未自动加载 `.env` 文件**，本地调试时可通过 `export VAR=...` 或使用进程管理工具加载环境变量。

### 2.3 启动后端

```bash
cd backend
# 默认在 8000 端口启动
uvicorn main:app --reload --port 8000
```

健康检查：

- `GET /v1/ping` → `{ "status": "ok" }`
- `GET /v1/providers` → 当前 Provider 模式，如 `{ "llm": "mock", ... }`

### 2.4 API 契约概览

**1）上传图片**

- `POST /api/upload-image`
- 请求：`multipart/form-data`，字段 `file`（图片文件）
- 响应：`{ "url": "/static/xxx.png" }`

**2）关系解析**

- `POST /api/parse-relation`
- 请求体（JSON）：
  ```json
  {
    "primary_relation": "亲戚 | 朋友 | 同事 | 师生",
    "secondary_relation": "长辈 / 密友 / 领导 ...",
    "custom_relation_text": "可选，自定义关系说明",
    "user_text": "可选，用户补充描述"
  }
  ```
- 响应：`{ "relation": { primary_key, secondary_key, primary_label, secondary_label, description } }`

**3）图片分析（视觉理解）**

- `POST /api/analyze-image`
- 请求体（JSON）：`{ "image_url": "/static/xxx.png" }`
- 响应：`{ "description": "对朋友圈截图的自然语言描述" }`

**4）祝福语生成**

- `POST /api/generate-blessing`
- 请求体（JSON）：
  ```json
  {
    "relation": { "primary_key": "family", "secondary_key": "elder", ... },
    "personality_profile": "可选，性格画像",
    "personality_tags": ["乐观开朗", "稳重靠谱"]
  }
  ```
- 响应：`{ "blessingText": "完整祝福语" }`

**5）绘图 Prompt 生成**

- `POST /api/generate-prompt`
- 请求体（JSON）：
  ```json
  {
    "relation": { ... },
    "personality_profile": "性格画像",
    "blessing_text": "祝福语",
    "image_description": "朋友圈内容描述，可选",
    "style_key": "auto | guofeng | cyberpunk | handwritten"
  }
  ```
- 响应：`{ "prompt": "适合文生图的详细指令" }`

**6）贺卡图片生成**

- `POST /api/generate-card`
- 请求体（JSON）：`{ "prompt": "...", "style_key": "..." }`
- 响应：`{ "cardImageUrl": "/static/mock_card.png" }`（Mock 模式下为占位路径）

**7）一键生成（前端主要使用）**

- `POST /api/generate`
- 请求：`multipart/form-data`
  - `primary_relation`：一级关系（如 `亲戚`、`朋友`、`同事`、`师生`）
  - `secondary_relation`：二级关系（如 `长辈`、`密友`、`领导` 等）
  - `custom_relation_text`：自定义说明（可选）
  - `personality_tags`：性格标签数组的 JSON 字符串或逗号分隔字符串
  - `style_key`：`auto | guofeng | cyberpunk | handwritten`
  - `mode`：`relation` / `image`（当前仅作透传，不强校验）
  - `file`：朋友圈截图（可选）
- 响应：
  ```json
  {
    "blessingText": "生成的祝福语文本",
    "cardImageUrl": "/static/mock_card.png" 或其他图片地址,
    "imageUrl": "/static/上传的图片路径，可为空",
    "relation": { ... 结构化关系信息 ... },
    "personalityProfile": "性格画像描述",
    "imageDescription": "图片内容描述",
    "providers": { "llm": "mock", "vision": "mock", "t2i": "mock", "storage": "mock" }
  }
  ```

> **Mock 模式说明**：当 `*_PROVIDER=mock` 或对应 `*_API_KEY` 留空时，后端会使用本地模板与规则生成内容，保证接口可用；后续接入真实服务时，只需在 `backend/providers/*.py` 内对 `SimpleHTTP*Provider` 实现进行补充，无需修改接口路径与入参。

---

## 3. 前端：React + Vite 单页应用

### 3.1 安装依赖

```bash
cd newyear-card
pnpm install
```

### 3.2 配置后端地址

```bash
cd newyear-card
cp .env.example .env
# 若后端部署到其他地址，修改 VITE_API_BASE 即可
```

`.env.example`：

```bash
VITE_API_BASE=http://localhost:8000
```

### 3.3 本地开发与构建

```bash
# 开发模式
cd newyear-card
pnpm run dev   # 浏览器访问 http://localhost:5173

# 生产构建
pnpm run build # 产物位于 newyear-card/dist
```

前端主要逻辑集中在 `src/App.tsx`：

- Hero 区：
  - 简介 + 三步流程概览
  - 右侧静态预览卡片
- 主操作卡片：
  - 输入方式 Tabs：
    - `只选关系`（仅关系 + 性格标签）
    - `关系 + 朋友圈截图`
  - 关系选择表单：一级（亲戚 / 朋友 / 同事 / 师生）+ 二级（长辈 / 密友 / 领导等）+ 自定义说明
  - 性格标签多选：如「温柔细腻」「乐观开朗」等
  - 贺卡风格选择：`auto / guofeng / cyberpunk / handwritten`
  - 图片上传组件：在「关系 + 朋友圈截图」模式下展示
  - 生成按钮 + 加载进度条 + 错误提示
  - Mock 模式提示：根据 `/v1/providers` 与 `/api/generate` 返回的 `providers` 字段判断
  - 结果区：
    - 祝福语展示 + 一键复制
    - 贺卡预览：
      - Mock 模式下使用前端 Canvas 合成图片并导出为 Data URL
      - 如果后端返回真实 `cardImageUrl`，也会自动展示
    - 图片下载按钮：优先下载 Canvas 合成图片
- 模板画廊：3 个典型场景（长辈国风、密友赛博、师生手写）
- FAQ + 隐私说明 + Footer

> 前端仅依赖 `VITE_API_BASE` 这一项环境变量。切换后端部署地址时，无需修改代码。

---

## 4. Provider 抽象与接入真实服务

所有外部能力都通过 `backend/providers/` 目录下的 Provider 封装：

- `llm.py`：关系解析、性格分析、祝福语生成、绘图 Prompt 生成
- `vision.py`：朋友圈截图的视觉理解 / OCR
- `t2i.py`：文生图（生成贺卡图片）
- `storage.py`：对象存储（上传图片 / 生成静态访问 URL）

每个 Provider 都包含：

- `Mock*Provider`：本地规则 / 模板实现，`*_PROVIDER=mock` 或无密钥时默认使用。
- `SimpleHTTP*Provider`：为接入真实服务预留的骨架类，当前仍调用 mock 逻辑，方便后续扩展。

接入真实服务的典型步骤：

1. 在对应 Provider 文件中（如 `llm.py` 的 `SimpleHTTPLLMProvider`）补充具体 HTTP 调用逻辑：
   - 支持关系解析、性格分析、祝福语生成等子任务；
   - 可根据需要拆分为多个 Prompt，或将现有本地模板作为系统提示的一部分。
2. 在部署环境中配置：
   - `LLM_PROVIDER=doubao`（举例）
   - `LLM_API_KEY=...`（真实密钥）
3. 重启后端服务。前端 **无需改动**，只会通过 `providers.llm` 看到从 `mock` 切换到具体 Provider 名称。

同理，可在 `vision.py` 中接入火山方舟视觉 / 内部 OCR 服务，在 `t2i.py` 中接入 `doubao-seedream` 或其他文生图模型，在 `storage.py` 中接入公司统一对象存储。

---

## 5. 部署与访问

### 5.1 后端部署（示意）

> 当前任务仅要求本地运行说明，因此这里给出通用步骤，实际部署可按公司基础设施调整。

1. 将 `backend` 目录连同 `requirements.txt`、`main.py`、`providers/`、`data/` 一并部署到服务器。
2. 安装依赖并配置环境变量（建议使用 `.env` 或服务管理器配置）：
   ```bash
   pip install -r requirements.txt
   ```
3. 启动服务（示例）：
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
4. 将对外地址写入前端 `.env` 的 `VITE_API_BASE` 中。

### 5.2 前端部署

1. 构建产物：
   ```bash
   cd newyear-card
   pnpm run build
   ```
2. 部署 `newyear-card/dist` 目录为静态站点，确保：
   - `index.html` 位于部署根目录；
   - 所有打包后的 `assets/*` 资源与 `index.html` 同域；
   - 若有额外静态资源（如自定义 JSON / 图片），放在与 `index.html` 同级目录下引用（避免使用 `../` 路径）。

本任务已经使用自动化工具对前端 `dist` 目录进行部署，并会在回复中附上访问链接。

---

## 6. 风险与注意事项

1. **中文 OCR / 视觉理解准确率**：
   - Mock 模式下仅返回通用描述，不做真实识别；
   - 接入真实视觉模型后，需根据业务评估误识别可能带来的语义偏差。
2. **隐私与截图内容**：
   - 建议用户仅上传模糊处理后的朋友圈截图，避免直接暴露头像、昵称、聊天记录等隐私信息；
   - 后端默认写入本地 `static` 目录，生产环境应替换为带过期策略与访问控制的对象存储。
3. **图片清晰度与分享体验**：
   - 前端 Canvas 合成的贺卡分辨率默认为竖版手机屏幕尺寸，适合微信发送；
   - 接入文生图时需注意生成分辨率与文件大小，避免在弱网环境中加载过慢。
4. **移动端适配**：
   - 页面已针对窄屏进行布局优化，但仍建议上线前在常见机型上做一次真机检查。
5. **分享给他人 / 手机端使用**：
   - **可以发给别人用**：需将前端与后端部署到公网（见 5.1、5.2），把访问链接发给对方即可。对方无需安装，浏览器打开即可使用。
   - **支持手机端打开**：前端已设 viewport、响应式布局与触控友好控件；同一套页面在手机浏览器中会自适应为上下结构，上传截图、选祝福语、生成贺卡、下载图片均可正常使用。部署后用手机浏览器访问同一链接即可。
6. **密钥安全**：
   - 所有密钥应仅配置在后端运行环境，不应写死在前端代码或 `.env` 中；
   - 前端只通过 `VITE_API_BASE` 访问后端，所有敏感调用都在后端完成。

如需进一步扩展（例如：账号体系、历史记录列表、多语言祝福、模板管理后台等），可以在当前接口与 Provider 抽象的基础上继续演进，无需破坏现有前后端契约。
