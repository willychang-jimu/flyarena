# 自訂果蠅頭像

1. 把圖片放在這個資料夾，例如 `avatars/淺酌.png`（支援 png、jpg、webp、svg，建議正方形、至少 96×96）。
2. 打開 `leagues/<聯賽名稱>/profiles.json`，找到那隻果蠅，把 `"avatar": null` 改成 `"avatar": "淺酌.png"`。
3. 執行 `.venv\Scripts\python -m flyarena site <聯賽名稱> --offline` 重建 dashboard。

同一個檔案裡也可以改 `nickname`（暱稱）、`title`（個性類型）、`emoji`、`bio`（介紹）。
改過的欄位不會被每天的自動更新覆蓋；想恢復自動產生，把該欄位整行刪掉即可。

注意：dashboard 公開在 GitHub 上時，這些圖片也會公開，請使用你有權使用的圖片。
