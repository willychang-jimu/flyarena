# 自訂果蠅頭像

1. 把圖片放在這個資料夾，例如 `avatars/淺酌.png`（支援 png、jpg、webp、svg，建議正方形、至少 96×96）。
2. 打開 `leagues/<聯賽名稱>/profiles.json`，找到那隻果蠅，把 `"avatar": null` 改成 `"avatar": "淺酌.png"`。
   （`null` 代表使用程式自動生成的卡通果蠅頭像。）
3. 想先在本機看效果：`python -m flyarena site <聯賽名稱> --offline`，打開 `preview/index.html`。
4. 確認沒問題後，commit 並推送圖片與 `profiles.json`（推送前先 `git pull`）。
   也可以不用電腦：直接在 GitHub 網頁上傳圖片、編輯 `profiles.json`。下次雲端執行就會出現在公開網站。

同一個檔案裡也可以改 `nickname`（暱稱）、`title`（個性類型）、`emoji`、`bio`（介紹）。
改過的欄位不會被每天的自動更新覆蓋；想恢復自動產生，把該欄位整行刪掉即可。

注意：公開網站上的圖片任何人都看得到，請使用你有權使用的圖片。
