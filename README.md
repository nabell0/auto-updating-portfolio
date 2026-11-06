# auto-updating-portfolio

리추얼 기록 CSV를 집계해 수치와 능력별 문단 후보를 만드는 프로그램이다. 집계는 파일 안의 행만 사용한다. 외부 모델을 부르지 않으므로, 같은 `new_records.csv`를 넣으면 `portfolio_update.json`과 `ability_candidates.md`가 항상 같다.

API 키는 코드에 적혀 있지 않다. 환경에 `API_KEY`가 있어도 `os.environ.get("API_KEY")`로 읽기만 하고, 수치와 문단에는 넣지 않는다. 키가 없을 때도 같은 파일이 나온다.

## 새 임시 폴더에서 실행하는 방법

프로젝트 폴더에서 아래 세 단계만 실행한다.

1. 빈 폴더를 만들고 스크립트와 기록 파일만 복사한다.

```powershell
New-Item -ItemType Directory -Force temp-portfolio | Out-Null
Copy-Item update_portfolio.py,new_records.csv temp-portfolio
Set-Location temp-portfolio
```

2. 기록 파일을 넣어 한 번 실행한다. 현재 폴더에 `portfolio_update.json`과 `ability_candidates.md`가 생긴다.

```powershell
python update_portfolio.py new_records.csv
```

3. 같은 명령을 한 번 더 실행한다. 화면에 찍힌 `sha256` 두 줄이 2단계와 글자 하나까지 같으면 통과다. 다르면 집계가 흔들린 것이다.

```powershell
python update_portfolio.py new_records.csv
```

사이트의 13주 기록 칸까지 이 수치로 바꾸려면, 표시 `<!-- PORTFOLIO_STATS_START -->`가 있는 `index.html`을 복사한 뒤 다음을 실행한다. 세 단계 확인에는 넣지 않는다.

```powershell
python update_portfolio.py new_records.csv --html index.html
```

## CSV 열

`date`, `evidence`는 필수다. `kind`는 `ritual` 또는 `submission`이고, 비우면 `ritual`이다. `ability`는 `자기조절력`, `대인관계력`, `자기동기력` 중 하나다. 비우면 근거 문장의 정해진 단어로 능력을 정한다. `source`는 문단에 그대로 실린다.
