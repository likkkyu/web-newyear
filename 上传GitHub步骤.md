# 将本项目上传到 GitHub 的操作步骤

---

## 1. 在项目目录初始化 Git（本机终端执行）

```bash
cd "/Users/likeyu/个人/自己玩的"
git init
```

## 2. 添加所有文件并做首次提交

```bash
git add .
git status
git commit -m "feat: 马年祝福贺卡生成器 - 多模态提取、三类祝福语、文生图贺卡与异常兜底"
```

说明：`.gitignore` 已配置，会排除 `node_modules/`、`venv/`、`.env`、`__pycache__/`、`dist/` 等，避免把依赖和密钥提交上去。

## 3. 在 GitHub 上新建仓库

1. 打开 https://github.com/new
2. 填写仓库名（如 `cny-card-agent` 或 `newyear-blessing-card`）
3. 选择 **Public**，**不要**勾选 "Add a README"（本地已有代码）
4. 点击 **Create repository**

## 4. 关联远程仓库并推送

将下面命令里的 `你的用户名` 和 `仓库名` 换成你自己的：

```bash
git remote add origin https://github.com/你的用户名/仓库名.git
git branch -M main
git push -u origin main
```

若使用 SSH：

```bash
git remote add origin git@github.com:你的用户名/仓库名.git
git branch -M main
git push -u origin main
```

首次 push 时可能弹出浏览器或命令行登录 GitHub，按提示完成即可。

## 5. 可选：检查是否漏提交敏感文件

推送前可确认 `.env` 未被加入（不应出现在 `git status` 里）：

```bash
git status
git check-ignore -v .env   # 应显示被 .gitignore 忽略
```

---

完成后，在 GitHub 仓库页即可看到完整代码。之后修改代码可：

```bash
git add .
git commit -m "简短描述本次修改"
git push
```
