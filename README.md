## Tailwind CSS 빌드

# npm 설치

https://nodejs.org → LTS 버전 설치

# tailwind css 설치

npm install

# 개발 시

npx tailwindcss -i ./styles/input.css -o ./static/css/main.css --watch

# 배포 시

npx tailwindcss -i ./styles/input.css -o ./static/css/main.css --minify
