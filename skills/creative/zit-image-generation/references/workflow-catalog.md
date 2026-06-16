# Workflow Catalog

## Overview

此 skill 目前內建三個固定 workflows：
- `rosie`
- `deepnight`
- `general`

選擇原則非常單純：
- **只要圖片內容和 Rosie 明確有關，就用 `rosie`**
- **只要使用者明確要求 deepnight，或需求核心是深夜氛圍內容，就用 `deepnight`**
- **其他一般情況都用 `general`**

---

## `rosie`

- 類型：Rosie 專用
- 用途：Rosie 本人相關的照片或圖片
- 適用情況：
  - 使用者明確要求生成 Rosie / 許御琪 / 御琪 / 小琪 / Rosie 相關圖片
  - 圖中主體是 Rosie
  - 畫面中明確包含 Rosie
- 不適用情況：
  - 一般人物、商品、場景、概念圖，且與 Rosie 無關
- 常用 args：
  - `user_prompt`
  - `width`
  - `height`
  - `seed`
  - 其他 schema 已暴露參數
- 固定 prompt 規則：
  - `user_prompt` 開頭固定為 `A young asian woman rosie_hsu, `
  - 使用者整理後的英文描述接在這段固定前綴後面
- Seed policy：
  - 若未指定，使用 `0 ~ 1125899906842624` 的隨機整數
- 尺寸預設：
  - `1024 x 1024`
- 備註：
  - 只要需求明確和 Rosie 有關，優先使用這個 workflow

---

## `deepnight`

- 類型：深夜內容專用
- 用途：深夜、微醺、夢境感、夜色主導的照片或圖片生成
- 適用情況：
  - 使用者明確指定 `deepnight`
  - 使用者明確提到深夜內容
  - 訊息出現 `deepnight`、`deep night`、`deep-night`
  - 需求氛圍明顯是深夜、昏暗、私密、夢境感
- 不適用情況：
  - 單純一般人物、場景、概念圖，且沒有深夜內容重點
- 常用 args：
  - `user_prompt`
  - `width`
  - `height`
  - `seed`
  - 其他 schema 已暴露參數
- Seed policy：
  - 若未指定，使用 `0 ~ 1125899906842624` 的隨機整數
- 尺寸預設：
  - `1024 x 1024`
- 備註：
  - 若使用者明確指定 workflow，優先照用

---

## `general`

- 類型：一般用途
- 用途：非 Rosie、非 deepnight 的一般照片或圖片生成
- 適用情況：
  - 一般人物照
  - 場景圖
  - 概念圖
  - 商品或其他與 Rosie 無關的圖像需求
- 不適用情況：
  - 明確要求 Rosie 出現在畫面中
  - 明確要求 deepnight 或深夜內容氛圍
- 常用 args：
  - `prompt`
  - `width`
  - `height`
  - `seed`
  - 其他 schema 已暴露參數
- Seed policy：
  - 若未指定，使用 `0 ~ 1125899906842624` 的隨機整數
- 尺寸預設：
  - `1024 x 1024`
- 備註：
  - 無法判定為 Rosie 或 deepnight 相關時，預設使用這個 workflow

---

## Selection Summary

依照以下順序選：

1. 使用者明確指定 `rosie`、`deepnight` 或 `general` 時，優先照用
2. 若需求明確和 Rosie 有關，使用 `rosie`
3. 若需求明確提到深夜內容，或出現 `deepnight` / `deep night` / `deep-night` 等關鍵字，使用 `deepnight`
4. 其他情況使用 `general`
