# 4. 조직도

## 4.1 조직도 조회 - GET /api/portal/common/organization/tree

조직도 API는 두 가지 모드로 호출한다. 어느 모드든 응답은
`data.elements[]`에 트리 노드를 담아 돌려주며, 각 노드의 `nodeType`이
`COMPANY` / `DEPARTMENT` / `MEMBER` 셋 중 하나다. 자식 노드는
`childrenList[]`로 중첩되며, MEMBER 노드는 사용자 한 명의 완전한
프로필 레코드다.

### 4.1.1 부서 단위 조회 (`rootDepartmentId`)

```
GET /api/portal/common/organization/tree?
  rootDepartmentId=11000015511&
  shouldApplyOrganizationChartExpansion=true
Cookie: AccessToken=...
```

해당 부서를 루트로 한 트리를 반환한다.

### 4.1.2 사용자 위치 조회 (`targetUserId`)

```
GET /api/portal/common/organization/tree?
  targetUserId=11000022612&
  shouldApplyOrganizationChartExpansion=true
Cookie: AccessToken=...
```

지정한 user_id가 속한 부서를 펼친 트리를 반환한다. 응답에는 대상
사용자 본인 + 같은 부서 동료들의 MEMBER 레코드가 포함된다. user_id로부터
이메일/loginId 등을 역해석할 때 사용한다 — SDK는 이 형태를 감싸
`BotClient.get_user(user_id)` 메서드로 노출한다.

### Response (capture-verified)

```json
{
  "data": {
    "elements": [
      {
        "id": "11000007240",
        "name": "기웅정보통신(주)",
        "nodeType": "COMPANY",
        "childrenList": [
          {
            "id": "11000020511",
            "name": "데이터팀",
            "nodeType": "DEPARTMENT",
            "departmentId": "11000020511",
            "childrenList": [
              {
                "id": "1493067168663818240",
                "name": "박준식",
                "nodeType": "MEMBER",
                "userId": "11000022612",
                "loginId": "junsik.park",
                "email": "junsik.park@kwic.co.kr",
                "userStatus": "NORMAL",
                "employeeNumber": "2315",
                "positionName": "부장",
                "dutyName": "팀장",
                "departmentId": "11000020511",
                "departmentName": "데이터팀",
                "departmentNamePath": "기웅정보통신(주) > 데이터솔루션센터 > 데이터팀",
                "profileImagePath": "OPERATION-.../87B0...3983B"
              }
            ]
          }
        ]
      }
    ]
  }
}
```

### MEMBER 노드 필수 필드

| 필드 | 의미 |
|---|---|
| `userId` | 플랫폼 user_id — inbound 메시지의 `sender_user_id`와 동일 키 |
| `loginId` | DaouOffice 로그인 ID (영문) |
| `name` | 사용자 표시 이름 |
| `email` | 회사 메일 |
| `userStatus` | `NORMAL` / `INACTIVE` 등 |
| `employeeNumber` | 사번 (없으면 `null`) |
| `positionName` / `dutyName` | 직위 / 직책 |
| `departmentId` / `departmentName` / `departmentNamePath` | 소속 부서 |
| `profileImagePath` | 프로필 이미지 경로 (없으면 `null`) |

---

## 4.2 즐겨찾기 조직 - GET /api/portal/common/organization/tree/favorite/user

```
GET /api/portal/common/organization/tree/favorite/user
Cookie: AccessToken=...
```

## 4.3 조직도 설정 - POST /api/portal/admin/organization/chart/config

---
