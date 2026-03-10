import { useState } from "react"
import { Camera, Copy, Download, Loader2, Sparkles, Wand2 } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Toggle } from "@/components/ui/toggle"

import "./App.css"

const API_BASE = import.meta.env.VITE_API_BASE || 

type InputMode = "relation" | "image"

type ProvidersMeta = {
  llm?: string
  vision?: string
  t2i?: string
  storage?: string
}

const RELATION_SECONDARY_OPTIONS: Record<string, { value: string; label: string }[]> = {
  "亲戚": [
    { value: "长辈", label: "长辈" },
    { value: "平辈", label: "平辈" },
    { value: "晚辈", label: "晚辈" },
  ],
  "朋友": [
    { value: "普通朋友", label: "普通朋友" },
    { value: "密友", label: "密友" },
  ],
  "同事": [
    { value: "领导", label: "领导" },
    { value: "同级同事", label: "同级同事" },
    { value: "下级", label: "下级" },
  ],
  "师生": [
    { value: "老师", label: "老师" },
    { value: "学生", label: "学生" },
  ],
}

const PERSONALITY_TAGS = [
  "温柔细腻",
  "乐观开朗",
  "社交牛",
  "佛系松弛",
  "稳重靠谱",
  "理性冷静",
  "热情外向",
  "慢热真诚",
]

const STYLE_OPTIONS = [
  { value: "auto", label: "自动匹配", description: "根据关系与性格自动选择风格" },
  { value: "guofeng", label: "国风新年", description: "适合长辈和领导，红金典雅" },
  { value: "cyberpunk", label: "赛博酷炫", description: "适合朋友、同事，带霓虹感" },
  { value: "handwritten", label: "手写明信片", description: "温柔一点的手写卡片感" },
]

function App() {
  const [inputMode, setInputMode] = useState<InputMode>("image")
  const [primaryRelation, setPrimaryRelation] = useState<string>("")
  const [secondaryRelation, setSecondaryRelation] = useState<string>("")
  const [customRelation, setCustomRelation] = useState<string>("")
  const [selectedTags, setSelectedTags] = useState<string[]>([])
  const [styleKey, setStyleKey] = useState<string>("auto")

  const [imageFile, setImageFile] = useState<File | null>(null)
  const [imagePreview, setImagePreview] = useState<string | null>(null)

  const [isGenerating, setIsGenerating] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const [blessingText, setBlessingText] = useState<string>("")
  const [cardImageUrl, setCardImageUrl] = useState<string>("")
  const [copySuccess, setCopySuccess] = useState(false)

  // PRD 5.1 两阶段：三类祝福语 → 用户选一条 → 生成贺卡
  type BlessingOption = { style: string; text: string }
  const [blessingOptions, setBlessingOptions] = useState<BlessingOption[]>([])
  const [selectedBlessingIndex, setSelectedBlessingIndex] = useState<number | null>(null)
  const [generateContext, setGenerateContext] = useState<{
    relation: Record<string, unknown>
    personalityProfile?: string
    extraction?: Record<string, unknown>
    imageUrl?: string
  } | null>(null)
  const [blessingHistory, setBlessingHistory] = useState<BlessingOption[][]>([])
  const [currentHistoryIndex, setCurrentHistoryIndex] = useState(0)
  const [isGeneratingCard, setIsGeneratingCard] = useState(false)
  const [pronounReplaceFrom, setPronounReplaceFrom] = useState("")
  const [pronounReplaceTo, setPronounReplaceTo] = useState("")
  const [blessingSize, setBlessingSize] = useState<"小" | "中" | "大">("中")


  const selectedBlessingText = selectedBlessingIndex !== null && blessingOptions[selectedBlessingIndex]
    ? blessingOptions[selectedBlessingIndex].text
    : ""
  const displayBlessingText = blessingText || selectedBlessingText

  const resolveBackendUrl = (url: string) => {
    if (!url) return ""
    if (/^https?:\/\//i.test(url)) return url
    if (url.startsWith("/")) return `${API_BASE}${url}`
    return url
  }

  const handleToggleTag = (tag: string) => {
    setSelectedTags((prev) =>
      prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]
    )
  }

  const handleImageChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) {
      setImageFile(null)
      setImagePreview(null)
      return
    }
    setImageFile(file)
    const url = URL.createObjectURL(file)
    setImagePreview(url)
  }

  const simulateProgress = () => {
    setProgress(10)
    const steps = [30, 55, 75]
    steps.forEach((value, index) => {
      setTimeout(() => {
        setProgress((prev) => (prev < value ? value : prev))
      }, (index + 1) * 500)
    })
  }

  const handleGenerate = async (event: React.FormEvent) => {
    event.preventDefault()
    setError(null)
    setCopySuccess(false)
      setCardImageUrl("")
      setBlessingText("")
      setSelectedBlessingIndex(null)

    if (!primaryRelation) {
      setError("请先选择与对方的关系。")
      return
    }
    if (inputMode === "image" && !imageFile) {
      setError("请选择一张朋友圈截图。")
      return
    }

    setIsGenerating(true)
    setProgress(0)
    simulateProgress()

    try {
      const formData = new FormData()
      formData.append("primary_relation", primaryRelation)
      if (secondaryRelation) formData.append("secondary_relation", secondaryRelation)
      if (customRelation) formData.append("custom_relation_text", customRelation)
      if (selectedTags.length) {
        formData.append("personality_tags", JSON.stringify(selectedTags))
      }
      formData.append("style_key", styleKey)
      formData.append("mode", inputMode)
      if (imageFile) formData.append("file", imageFile)

      const response = await fetch(`${API_BASE}/api/generate`, {
        method: "POST",
        body: formData,
      })

      const rawBody = await response.text()
      let data: {
        blessingOptions?: BlessingOption[]
        relation?: Record<string, unknown>
        personalityProfile?: string
        extraction?: Record<string, unknown>
        imageUrl?: string
        providers?: ProvidersMeta
        useFallback?: boolean
        detail?: string
        message?: string
      } = {}
      try {
        data = JSON.parse(rawBody) as typeof data
      } catch {
        // ignore
      }

      if (!response.ok) {
        const msg = data?.detail || data?.message || `请求失败 ${response.status}`
        throw new Error(msg)
      }

      const options = data.blessingOptions || []
      setBlessingOptions(options)
      setBlessingHistory([options])
      setCurrentHistoryIndex(0)
      setGenerateContext({
        relation: data.relation || {},
        personalityProfile: data.personalityProfile,
        extraction: data.extraction,
        imageUrl: data.imageUrl,
      })
      if (data.useFallback) {
        setError("截图识别不足，已使用通用马年祝福语，可继续选择一条生成贺卡。")
      }
      setProgress(100)
    } catch (err: unknown) {
      const raw = err instanceof Error ? err.message : String(err)
      const isNetworkError =
        /load failed|failed to fetch|network error|网络错误/i.test(raw) || raw === ""
      setError(
        isNetworkError
          ? "网络请求失败，请确认后端已启动（在 backend 目录执行 uvicorn main:app --reload --port 8000）且前端访问地址正确。"
          : raw || "生成过程中出现错误。"
      )
    } finally {
      setIsGenerating(false)
      setTimeout(() => setProgress(0), 800)
    }
  }

  const handleRegenerateBlessings = async () => {
    if (!generateContext) return
    setError(null)
    setIsGenerating(true)
    try {
      const res = await fetch(`${API_BASE}/api/regenerate-blessings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          relation: generateContext.relation,
          personality_profile: generateContext.personalityProfile,
          personality_tags: selectedTags,
        }),
      })
      const raw = await res.text()
      let data: { blessingOptions?: BlessingOption[]; detail?: string } = {}
      try {
        data = JSON.parse(raw)
      } catch {
        // ignore
      }
      if (!res.ok) throw new Error(data?.detail || raw || "重新生成失败")
      const options = data.blessingOptions || []
      setBlessingOptions(options)
      setBlessingHistory((prev) => {
        const next = [...prev, options]
        setCurrentHistoryIndex(next.length - 1)
        return next
      })
      setSelectedBlessingIndex(null)
      setCardImageUrl("")
      setBlessingText("")
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "重新生成失败")
    } finally {
      setIsGenerating(false)
    }
  }

  const handleGenerateCard = async () => {
    if (selectedBlessingIndex == null || !blessingOptions[selectedBlessingIndex] || !generateContext) {
      setError("请先选择一条祝福语再生成贺卡。")
      return
    }
    let text = blessingOptions[selectedBlessingIndex].text
    if (pronounReplaceFrom.trim() && pronounReplaceTo.trim()) {
      text = text.replace(new RegExp(pronounReplaceFrom.trim().replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "g"), pronounReplaceTo.trim())
    }
    setError(null)
    setIsGeneratingCard(true)
    try {
      const res = await fetch(`${API_BASE}/api/generate-card`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          selected_blessing_text: text,
          style_key: styleKey,
          relation: generateContext.relation,
          personality_profile: generateContext.personalityProfile,
          extraction: generateContext.extraction,
          image_description: generateContext.extraction
            ? [
                (generateContext.extraction as Record<string, string>).avatar_desc,
                (generateContext.extraction as Record<string, string>).background_desc,
              ]
              .filter(Boolean)
              .join("；")
            : undefined,
          blessing_size: blessingSize,
        }),
      })
      const raw = await res.text()
      let data: { cardImageUrl?: string; detail?: string } = {}
      try {
        data = JSON.parse(raw)
      } catch {
        // ignore
      }
      if (!res.ok) throw new Error(data?.detail || raw || "贺卡生成失败")
      const cardUrl = resolveBackendUrl(data.cardImageUrl || "")
      setCardImageUrl(cardUrl)
      setBlessingText(text)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "贺卡生成失败")
    } finally {
      setIsGeneratingCard(false)
    }
  }

  const handleCopy = async () => {
    const toCopy = displayBlessingText || blessingText
    if (!toCopy) return
    try {
      await navigator.clipboard.writeText(toCopy)
      setCopySuccess(true)
      setTimeout(() => setCopySuccess(false), 1500)
    } catch {
      setCopySuccess(false)
    }
  }

  const handleDownload = () => {
    const url = cardImageUrl
    if (!url) return
    const link = document.createElement("a")
    link.href = url
    link.download = "newyear-card.png"
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const hasResult = blessingOptions.length > 0 || !!blessingText

  return (
    <div className="min-h-screen bg-gradient-to-b from-amber-50 via-white to-rose-50 text-slate-900 relative">
      {/* 两侧马与祥云线稿暗纹（unnamed.jpg），低透明度 */}
      <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
        <div
          className="absolute left-0 top-0 h-full w-[min(28vw,420px)] opacity-[0.12]"
          style={{
            backgroundImage: "url(/horse-pattern.jpg)",
            backgroundRepeat: "repeat",
            backgroundSize: "auto 280px",
          }}
        />
        <div
          className="absolute right-0 top-0 h-full w-[min(28vw,420px)] opacity-[0.12]"
          style={{
            backgroundImage: "url(/horse-pattern.jpg)",
            backgroundRepeat: "repeat",
            backgroundSize: "auto 280px",
          }}
        />
      </div>

      <header className="relative z-10 border-b border-amber-100 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-rose-400 text-white shadow-md">
            <Sparkles className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-lg font-semibold tracking-tight text-slate-900">马年朋友圈祝福贺卡生成器</h1>
            <p className="text-xs text-slate-500">选择关系或上传截图，一键生成祝福语与贺卡。</p>
          </div>
        </div>
      </header>

      <main className="relative z-10 mx-auto flex max-w-5xl flex-col gap-8 px-4 py-8 pb-16">
        {/* 主操作：表单 + 结果展示 */}
        <Card className="border-none bg-white/90 shadow-xl shadow-amber-100/80">
          <CardHeader className="border-b border-amber-50 pb-4">
            <div>
              <CardTitle className="text-base font-semibold">填写信息 · 一键生成</CardTitle>
              <CardDescription className="text-xs">
                请选择你与对方的关系，可勾选性格标签或上传朋友圈截图，让祝福语更贴近对方。
              </CardDescription>
            </div>
          </CardHeader>

          <CardContent className="pt-6">
            <div className="grid gap-8 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1.2fr)]">
              {/* 左侧：输入表单 */}
              <section className="space-y-6">
                <form className="space-y-6" onSubmit={handleGenerate}>
                  <div className="space-y-2">
                    <Label className="text-xs font-medium text-slate-700">
                      输入方式
                    </Label>
                    <Tabs
                      value={inputMode}
                      onValueChange={(value) => setInputMode(value as InputMode)}
                      className="w-full"
                    >
                      <TabsList className="grid w-full grid-cols-2">
                        <TabsTrigger value="relation" className="text-xs">
                          只选关系
                        </TabsTrigger>
                        <TabsTrigger value="image" className="text-xs">
                          关系 + 朋友圈截图
                        </TabsTrigger>
                      </TabsList>
                      <TabsContent value="relation" className="pt-4 text-xs text-slate-500">
                        适合已经很了解对方的场景，仅根据关系和性格标签生成内容。
                      </TabsContent>
                      <TabsContent value="image" className="pt-4 text-xs text-slate-500">
                        会先解析朋友圈截图，再结合关系生成更贴近对方状态的祝福语和贺卡。
                      </TabsContent>
                    </Tabs>
                  </div>

                  {/* 关系选择 */}
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label className="text-xs">一级关系</Label>
                      <Select
                        value={primaryRelation}
                        onValueChange={(value) => {
                          setPrimaryRelation(value)
                          setSecondaryRelation("")
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="选择关系类型" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="亲戚">亲戚</SelectItem>
                          <SelectItem value="朋友">朋友</SelectItem>
                          <SelectItem value="同事">同事</SelectItem>
                          <SelectItem value="师生">师生</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-1.5">
                      <Label className="text-xs">二级关系</Label>
                      <Select
                        value={secondaryRelation}
                        onValueChange={(value) => setSecondaryRelation(value)}
                        disabled={!primaryRelation}
                      >
                        <SelectTrigger>
                          <SelectValue placeholder="选择更具体的关系" />
                        </SelectTrigger>
                        <SelectContent>
                          {(RELATION_SECONDARY_OPTIONS[primaryRelation] || []).map((opt) => (
                            <SelectItem key={opt.value} value={opt.value}>
                              {opt.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <Label className="text-xs">补充说明（可选）</Label>
                    <Input
                      placeholder="例如：一起打 ranked 的密友 / 初中班主任 / 带我入职的前辈…"
                      value={customRelation}
                      onChange={(e) => setCustomRelation(e.target.value)}
                    />
                  </div>

                  {/* 性格标签 */}
                  <div className="space-y-2">
                    <Label className="text-xs">性格标签（可多选）</Label>
                    <div className="flex flex-wrap gap-2">
                      {PERSONALITY_TAGS.map((tag) => {
                        const active = selectedTags.includes(tag)
                        return (
                          <Toggle
                            key={tag}
                            pressed={active}
                            onPressedChange={() => handleToggleTag(tag)}
                            className="h-7 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs text-amber-800 data-[state=on]:border-amber-500 data-[state=on]:bg-amber-100"
                          >
                            {tag}
                          </Toggle>
                        )
                      })}
                    </div>
                    <p className="text-[11px] text-slate-400">
                      不填也可以，默认会根据图片或关系使用较为通用的温柔语气。
                    </p>
                  </div>

                  {/* 风格选择 */}
                  <div className="space-y-1.5">
                    <Label className="text-xs">贺卡风格</Label>
                    <Select value={styleKey} onValueChange={setStyleKey}>
                      <SelectTrigger>
                        <SelectValue placeholder="选择贺卡整体风格" />
                      </SelectTrigger>
                      <SelectContent>
                        {STYLE_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            <div className="flex flex-col">
                              <span>{opt.label}</span>
                              <span className="text-[11px] text-slate-400">{opt.description}</span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* 图片上传（可选） */}
                  {inputMode === "image" && (
                    <div className="space-y-2">
                      <Label className="text-xs">朋友圈截图（可模糊处理后上传）</Label>
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                        <label className="flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-amber-200 bg-amber-50/70 px-3 py-2 text-xs text-amber-800 shadow-sm hover:bg-amber-100">
                          <Camera className="h-4 w-4" />
                          <span>{imageFile ? "重新选择图片" : "点击上传图片"}</span>
                          <input
                            type="file"
                            accept="image/*"
                            className="hidden"
                            onChange={handleImageChange}
                          />
                        </label>
                        {imagePreview && (
                          <div className="h-16 w-16 overflow-hidden rounded-lg border border-amber-100 bg-slate-100">
                            <img
                              src={imagePreview}
                              alt="朋友圈截图预览"
                              className="h-full w-full object-cover"
                            />
                          </div>
                        )}
                      </div>
                      <p className="text-[11px] text-slate-400">
                        建议仅保留大致画面氛围，必要时可打码处理，以保护对方隐私。
                      </p>
                      <p className="text-[11px] text-amber-700">
                        截图需包含四区域：头像、背景、个性签名、动态区，以便更准确提取信息。
                      </p>
                    </div>
                  )}

                  {/* 生成按钮与进度 */}
                  <div className="space-y-3 pt-2">
                    <Button
                      type="submit"
                      disabled={isGenerating}
                      className="w-full bg-gradient-to-r from-amber-500 to-rose-500 text-sm font-medium text-white shadow-md hover:from-amber-600 hover:to-rose-600"
                    >
                      {isGenerating ? (
                        <span className="flex items-center justify-center gap-2">
                          <Loader2 className="h-4 w-4 animate-spin" /> 正在为你构思祝福和贺卡…
                        </span>
                      ) : (
                        <span className="flex items-center justify-center gap-2">
                          <Wand2 className="h-4 w-4" /> 生成新年祝福语与贺卡
                        </span>
                      )}
                    </Button>
                    <div className="space-y-1 text-[11px] text-slate-400">
                      <p>生成过程通常需要 5–10 秒，请稍候，不要反复点击。</p>
                      {progress > 0 && (
                        <div className="flex items-center gap-2">
                          <Progress value={progress} className="h-1.5 flex-1" />
                          <span>{progress}%</span>
                        </div>
                      )}
                    </div>
                    {error && (
                      <Alert variant="destructive" className="border-rose-300 bg-rose-50 text-xs">
                        <AlertTitle>生成失败</AlertTitle>
                        <AlertDescription>{error}</AlertDescription>
                      </Alert>
                    )}
                  </div>
                </form>
              </section>

              {/* 右侧：结果展示 */}
              <section className="space-y-4">
                <div className="rounded-xl border border-amber-100 bg-amber-50/60 p-3 text-xs text-amber-900">
                  <p className="font-medium flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5" /> 生成结果
                  </p>
                  <p className="mt-1 text-[11px] text-amber-900/80">
                    这里会展示 AI 生成的祝福语和贺卡预览，你可以复制文本，或下载图片发送给对方。
                  </p>
                </div>

                <div className="space-y-4">
                  {/* 三类祝福语选择（PRD 4.5） */}
                  {blessingOptions.length > 0 && (
                    <Card className="border border-amber-100 bg-white/90">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">选择一条祝福语</CardTitle>
                        <CardDescription className="text-[11px]">
                          文言风 / 文艺风 / 大白话，选一条用于生成贺卡；可点击「重新生成」替换。
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        {blessingOptions.map((opt, idx) => (
                          <button
                            key={idx}
                            type="button"
                            onClick={() => {
                              setSelectedBlessingIndex(idx)
                              setCardImageUrl("")
                            }}
                            className={`w-full rounded-lg border p-3 text-left text-xs transition ${
                              selectedBlessingIndex === idx
                                ? "border-amber-500 bg-amber-50 text-amber-900"
                                : "border-amber-100 bg-white hover:bg-amber-50/50"
                            }`}
                          >
                            <span className="font-medium text-amber-800">{opt.style}：</span>
                            <span className="text-slate-700">{opt.text}</span>
                          </button>
                        ))}
                        <div className="flex flex-wrap items-center gap-2 pt-1">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="text-xs"
                            disabled={isGenerating}
                            onClick={handleRegenerateBlessings}
                          >
                            {isGenerating ? "生成中…" : "重新生成三条"}
                          </Button>
                          {blessingHistory.length > 1 && (
                            <Select
                              value={String(currentHistoryIndex)}
                              onValueChange={(v) => {
                                const idx = parseInt(v, 10)
                                if (idx >= 0 && blessingHistory[idx]) {
                                  setCurrentHistoryIndex(idx)
                                  setBlessingOptions(blessingHistory[idx])
                                  setSelectedBlessingIndex(null)
                                }
                              }}
                            >
                              <SelectTrigger className="h-8 w-auto min-w-[100px] text-xs">
                                <SelectValue placeholder="历史" />
                              </SelectTrigger>
                              <SelectContent>
                                {blessingHistory.map((_, idx) => (
                                  <SelectItem key={idx} value={String(idx)}>
                                    第 {idx + 1} 组
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* 手动调整（PRD 4.6.3）：风格已在顶部；祝福语大小、称呼替换 */}
                  {blessingOptions.length > 0 && selectedBlessingIndex !== null && (
                    <Card className="border border-amber-100 bg-white/90">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-sm">贺卡设置</CardTitle>
                        <CardDescription className="text-[11px]">
                          可选：祝福语大小、将祝福语中的称呼替换后写入贺卡（如 您→舅妈）。
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <div className="grid grid-cols-2 gap-2 text-xs">
                          <Label>祝福语大小</Label>
                          <Select
                            value={blessingSize}
                            onValueChange={(v) => setBlessingSize(v as "小" | "中" | "大")}
                          >
                            <SelectTrigger className="h-8">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="小">小</SelectItem>
                              <SelectItem value="中">中</SelectItem>
                              <SelectItem value="大">大</SelectItem>
                            </SelectContent>
                          </Select>
                          <Label>替换称呼（如 您→舅妈）</Label>
                          <div className="flex gap-1">
                            <Input
                              placeholder="您"
                              value={pronounReplaceFrom}
                              onChange={(e) => setPronounReplaceFrom(e.target.value)}
                              className="h-8 text-xs"
                            />
                            <span className="self-center text-slate-400">→</span>
                            <Input
                              placeholder="舅妈"
                              value={pronounReplaceTo}
                              onChange={(e) => setPronounReplaceTo(e.target.value)}
                              className="h-8 text-xs"
                            />
                          </div>
                        </div>
                        <Button
                          type="button"
                          className="w-full bg-gradient-to-r from-amber-500 to-rose-500 text-xs text-white"
                          disabled={isGeneratingCard}
                          onClick={handleGenerateCard}
                        >
                          {isGeneratingCard ? "正在生成贺卡…" : "生成贺卡"}
                        </Button>
                      </CardContent>
                    </Card>
                  )}

                  <Card className="border border-amber-100 bg-white/90">
                    <CardHeader className="pb-2">
                      <CardTitle className="flex items-center justify-between text-sm">
                        <span>祝福语</span>
                        {displayBlessingText && (
                          <div className="flex items-center gap-2">
                            <Button
                              type="button"
                              size="icon"
                              variant="outline"
                              className="h-7 w-7"
                              onClick={handleCopy}
                            >
                              <Copy className="h-3.5 w-3.5" />
                            </Button>
                            <span className="text-[11px] text-slate-400">
                              {copySuccess ? "已复制" : "一键复制"}
                            </span>
                          </div>
                        )}
                      </CardTitle>
                      <CardDescription className="text-[11px]">
                        已选或已写入贺卡的祝福语，可复制发送。
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <div className="rounded-md bg-slate-50/80 p-3 text-sm leading-relaxed text-slate-800">
                        {displayBlessingText ? (
                          <p>{displayBlessingText}</p>
                        ) : blessingOptions.length > 0 ? (
                          <p className="text-slate-400">请在上方选择一条祝福语，再点击「生成贺卡」。</p>
                        ) : (
                          <p className="text-slate-400">
                            选择关系（可上传截图）后点击「生成新年祝福语与贺卡」，将得到三条风格祝福语，选一条生成贺卡。
                          </p>
                        )}
                      </div>
                    </CardContent>
                  </Card>

                  <Card className="border border-amber-100 bg-white/90">
                    <CardHeader className="pb-2">
                      <CardTitle className="flex items-center justify-between text-sm">
                        <span>贺卡预览</span>
                        {cardImageUrl && (
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="gap-2 text-xs"
                            onClick={handleDownload}
                          >
                            <Download className="h-3.5 w-3.5" /> 下载图片
                          </Button>
                        )}
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="flex justify-center">
                        {cardImageUrl ? (
                          <div className="relative w-full max-w-xs">
                            <div className="relative overflow-hidden rounded-2xl border border-amber-100 bg-slate-100 shadow-md">
                              <img
                                src={cardImageUrl}
                                alt="新年贺卡预览"
                                className="block w-full"
                              />
                            </div>
                          </div>
                        ) : hasResult ? (
                          <div
                            className="flex aspect-[9/16] w-full max-w-[220px] flex-col items-center justify-center gap-2 rounded-2xl border border-amber-200/80 p-4 text-center text-xs text-slate-500"
                            style={{
                              background: "linear-gradient(145deg, #fef3c7 0%, #fde68a 50%, #fcd34d 100%)",
                            }}
                          >
                            <span className="rounded-full bg-white/50 px-2 py-0.5 font-medium text-amber-900">马年 · 2026</span>
                            <p>选择一条祝福语并点击「生成贺卡」后，此处显示贺卡预览。</p>
                          </div>
                        ) : (
                          <div
                            className="flex aspect-[9/16] w-full max-w-[220px] flex-col items-center justify-center gap-2 rounded-2xl border border-amber-200/80 text-center shadow-inner"
                            style={{
                              background: "linear-gradient(145deg, #fef3c7 0%, #fde68a 25%, #fcd34d 50%, #f59e0b 75%, #d97706 100%)",
                              boxShadow: "inset 0 0 60px rgba(251,191,36,0.2), 0 4px 12px rgba(0,0,0,0.06)",
                            }}
                          >
                            <span className="rounded-full bg-white/30 px-2 py-0.5 text-[10px] font-medium text-amber-900">
                              马年 · 2026
                            </span>
                            <p className="max-w-[160px] text-xs font-medium leading-snug text-amber-950/90">
                              生成后此处显示贺卡，祝福语将呈现在卡片上。
                            </p>
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </div>

              </section>
            </div>
          </CardContent>
        </Card>

        {/* 模板画廊 */}
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-800">灵感模板画廊</h3>
            <span className="text-[11px] text-slate-400">
              以下仅为灵感示例，实际内容会根据你的输入动态生成。
            </span>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <Card className="border border-amber-100 bg-white/90">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-amber-100 text-amber-700">
                    1
                  </span>
                  长辈 · 国风典雅
                </CardTitle>
                <CardDescription className="text-[11px]">
                  适合长辈、领导等正式场景，红金搭配、画面庄重。
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-xs leading-relaxed text-slate-600">
                  祝福语会以尊敬、感恩为主，强调「身体安康、阖家团圆、福寿绵长」，贺卡风格偏国风、红金配色，像正式的新年贺卡。
                </p>
              </CardContent>
            </Card>

            <Card className="border border-amber-100 bg-white/90">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-rose-100 text-rose-700">
                    2
                  </span>
                  密友 · 赛博夜景
                </CardTitle>
                <CardDescription className="text-[11px]">
                  搭配「乐观开朗」「社交牛」等标签时很适合。
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-xs leading-relaxed text-slate-600">
                  祝福语更偏真实与松弛，比如「继续做彼此的精神股东」，画面会是带霓虹灯的城市夜景、赛博风，适合发给关系很近的朋友。
                </p>
              </CardContent>
            </Card>

            <Card className="border border-amber-100 bg-white/90">
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-sm">
                  <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
                    3
                  </span>
                  师生 / 同事 · 手写卡片
                </CardTitle>
                <CardDescription className="text-[11px]">
                  适合老师、前辈、同事，语气真诚不油腻。
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-xs leading-relaxed text-slate-600">
                  文案会感谢对方这一年的陪伴或指导，风格类似手写明信片：淡色纸张背景 + 手写字效果，适合发给老师、mentor 或合作很久的同事。
                </p>
              </CardContent>
            </Card>
          </div>
        </section>

        {/* FAQ / 隐私说明 */}
        <section className="grid gap-6 md:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <div>
            <h3 className="mb-3 text-sm font-semibold text-slate-800">常见问题</h3>
            <Accordion type="single" collapsible className="space-y-2">
              <AccordionItem value="time">
                <AccordionTrigger className="text-xs">
                  生成一张贺卡大概需要多久？
                </AccordionTrigger>
                <AccordionContent className="text-xs text-slate-600">
                  通常为 5–10 秒，取决于关系与是否上传截图；文生图会略增加耗时，整体在可接受范围内。
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="quality">
                <AccordionTrigger className="text-xs">
                  上传朋友圈截图有什么作用？
                </AccordionTrigger>
                <AccordionContent className="text-xs text-slate-600">
                  会先分析截图内容与氛围，再结合你选择的关系与性格标签生成更贴合的祝福语和贺卡风格。
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="mobile">
                <AccordionTrigger className="text-xs">
                  这个页面在手机上也能正常使用吗？
                </AccordionTrigger>
                <AccordionContent className="text-xs text-slate-600">
                  页面布局已考虑移动端，会自动在窄屏下折叠为上下结构。实际投放前建议在多款机型上做一次
                  真机联调，重点关注图片清晰度和下载后的分享体验。
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </div>

          <div className="space-y-2 rounded-xl border border-slate-100 bg-white/90 p-4 text-xs text-slate-600">
            <div className="flex items-center gap-2">
              <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-slate-900 text-[10px] font-semibold text-amber-50">
                i
              </span>
              <h3 className="text-sm font-semibold text-slate-800">隐私与数据说明</h3>
            </div>
            <p>
              · 上传的朋友圈截图仅用于当前生成流程，不会被前端缓存；贺卡与截图可按后端配置写入对象存储。
            </p>
            <p>
              · 建议在正式对外开放前，与公司内的安全与合规同学一起确认：包含头像、昵称、聊天记录等敏感信息的截图是否需要额外脱敏或告知。
            </p>
            <p>
              · 如对数据存储方式有更高要求，可以在后端 Provider 层替换为公司统一的对象存储与日志体系，仅需修改
              providers/* 文件，无需改动前端与 API 契约。
            </p>
          </div>
        </section>

        <footer className="mt-4 border-t border-amber-100 pt-4 text-[11px] text-slate-500">
          <p>马年祝福贺卡生成器 · 祝福语与贺卡由 AI 生成，请勿用于商业用途。</p>
        </footer>
      </main>
    </div>
  )
}

export default App
