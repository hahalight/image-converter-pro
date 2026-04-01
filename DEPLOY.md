# 🚀 GitHub 배포 + Docker 빌드 가이드

## 1단계 — GitHub 리포지토리 생성 및 푸시

```powershell
# 프로젝트 폴더로 이동
cd image-converter

# Git 초기화 및 최초 커밋
git init
git add .
git commit -m "feat: initial release - Image Converter Pro v1.0.0"

# GitHub에서 새 리포지토리 생성 후 (예: image-converter-pro)
git remote add origin https://github.com/YOUR_USERNAME/image-converter-pro.git
git branch -M main
git push -u origin main
```

---

## 2단계 — GitHub Actions 자동 빌드 트리거

버전 태그를 푸시하면 Windows EXE + Linux 바이너리 + macOS 바이너리가
자동으로 빌드되고 GitHub Releases 페이지에 올라갑니다.

```powershell
# 릴리즈 태그 생성 및 푸시
git tag v1.0.0
git push origin v1.0.0
```

GitHub Actions 진행 상황: `Actions` 탭 → `Build & Release` 워크플로우

---

## 3단계 — Docker로 로컬 빌드 (Windows)

### 사전 준비
- Docker Desktop for Windows 설치 (WSL2 백엔드 권장)
- https://www.docker.com/products/docker-desktop

### Linux 바이너리 빌드

```powershell
# Docker 이미지 빌드 (linux-build 스테이지)
docker build --target linux-build -t imgconv-builder .

# 바이너리 추출 (현재 폴더의 dist/ 에 저장)
mkdir dist
docker run --rm -v "${PWD}/dist:/out" imgconv-builder

# 결과 확인
ls dist/
# → ImageConverterPro
```

### Windows EXE 빌드 (로컬, Docker 없이)

```powershell
# Python 3.11 설치 후
pip install -r requirements.txt
pip install pyinstaller

pyinstaller ImageConverterPro.spec --noconfirm

# 결과: dist/ImageConverterPro.exe
```

---

## 4단계 — 로컬 개발 환경 (소스 실행)

```powershell
# 의존성 설치
pip install -r requirements.txt

# 실행
python src/main.py
```

---

## 5단계 — 테스트 실행

```powershell
pip install pytest
pytest tests/ -v
```

---

## 프로젝트 구조

```
image-converter-pro/
├── src/
│   ├── main.py          ← 진입점
│   ├── converter.py     ← 변환 엔진 (GUI 의존 없음)
│   └── gui.py           ← Tkinter UI
├── tests/
│   └── test_converter.py
├── .github/
│   └── workflows/
│       └── build.yml    ← CI/CD (Windows/Linux/macOS 자동 빌드)
├── Dockerfile           ← 멀티스테이지 빌드
├── docker-compose.yml
├── ImageConverterPro.spec  ← PyInstaller 설정
├── requirements.txt
└── README.md
```

---

## GitHub Actions 빌드 매트릭스

| Runner | 출력 파일 | 방식 |
|--------|-----------|------|
| `windows-latest` | `ImageConverterPro-Windows-x64.zip` | PyInstaller 직접 |
| `ubuntu-latest` | `ImageConverterPro-Linux-x64.tar.gz` | Docker 컨테이너 |
| `macos-latest` | `ImageConverterPro-macOS-x64.zip` | PyInstaller 직접 |

릴리즈 태그 푸시 시 세 플랫폼 바이너리가 자동으로
GitHub Releases 페이지에 첨부됩니다.

---

## 주의사항

- `YOUR_USERNAME`을 실제 GitHub 계정명으로 교체하세요
- GitHub Actions 탭에서 `Build & Release` 워크플로우 활성화 확인
- Windows 방화벽/백신이 PyInstaller 빌드를 차단하면 예외 추가 필요
- AVIF 지원은 `pillow-avif-plugin` 설치 시 활성화됩니다
