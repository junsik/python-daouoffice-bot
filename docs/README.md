# 문서

- **[ARCHITECTURE.md](ARCHITECTURE.md)** — SDK가 어떻게, **왜** 그렇게 설계됐는지(결정·다이어그램). 프로젝트를 이해하려면 여기부터.
- **[api/](api/README.md)** — 역분석한 DaouOffice REST 엔드포인트 레퍼런스(인증, 채팅방, 메시지(멘션·첨부 포함), 미구현 WebSocket 메모, 포털/조직). SAZ 캡처에서 익명화한 샘플.

운영 메모: 번들된 systemd 유닛은 없다 — 봇 실행은 그냥 `python your_bot.py`(`DaouBot(on_message=...)`)이고, supervisor(systemd/Docker 등)는 쓰는 사람이 직접 감싼다.
