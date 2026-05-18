# 4. 조직도

## 4.1 조직도 조회 - GET /api/portal/common/organization/tree

### Request
```
GET /api/portal/common/organization/tree?
  rootDepartmentId=&
  shouldApplyOrganizationChartExpansion=true
Cookie: AccessToken=...
```

### Response (예상 구조)
```json
{
  "code": "SUCCESS-0000",
  "data": {
    "departmentId": "xxx",
    "departmentName": "개발팀",
    "children": [
      {
        "departmentName": "백엔드팀",
        "parentDepartmentName": null,
      }
    ],
    "members": []
  }
  ]
}
```

---

## 4.2 즐겨찾리 조직 - GET /api/portal/common/organization/tree/favorite/user

```
GET /api/portal/common/organization/tree/favorite/user
Cookie: AccessToken=...
```

## 4.3 조직도 설정 - POST /api/portal/admin/organization/chart/config

---
