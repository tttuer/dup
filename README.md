## Tailwind CSS 빌드

# 개발 시

npx tailwindcss -i ./styles/input.css -o ./static/css/main.css --watch

# 배포 시

npx tailwindcss -i ./styles/input.css -o ./static/css/main.css --minify
