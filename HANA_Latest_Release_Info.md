# SAP HANA Latest Release Information (HEC/ECS)
**Source:** [DB BB HANA DB Versions](https://wiki.one.int.sap/wiki/pages/releaseview.action?pageId=1617468855#DBBBHANADBVersions-HANA2.0VersionReleaseInformation)  
**Page Version:** 623 | **Last Updated by:** Tijare, Shruti (C5404202) | **Date:** 2026-06-29  
**Report Generated:** 2026-07-30

---

## ECS Standard Releases

| Release Slot | HANA Version | SAP Note | Status | Recommended OS |
|---|---|---|---|---|
| **Release (N) — Current Standard** | **SAP HANA 2.0 SPS08 Rev 089.03** | 3737608 | ✅ Available for ECS Customers | SLES 15 SP5+ / RHEL 9.2+ |
| **Release (N-1)** | **SAP HANA 2.0 SPS07 Rev 079.09** | 3698808 | ✅ Available for ECS Customers | SLES 15 SP4+ |
| **Next Planned Release** | SAP HANA 2.0 SPS08 Rev 089.0x | TBD | Planned | — |

---

## HANA 2.0 SPS08 Revision Status

| Revision | SAP Note | ECS Status | Standard Version? | Notes |
|---|---|---|---|---|
| **Rev 089.03** ← **N (Current)** | 3737608 | ✅ Available for ECS Customers | **Yes** | Upgrade from Rev 079.09 supported |
| Rev 089.02 | 3714686 | — | — | — |
| Rev 089.01 | 3700300 | — | — | — |
| Rev 089.00 | 3672906 | Available for ECS from target date | — | — |
| Rev 088.00 | 3645031 | — | Yes | — |
| Rev 087.00 | 3623156 | ❌ Not recommended | Yes | No |
| Rev 086.00 | 3602844 | ❌ Not recommended | Yes | No |
| Rev 085.00 | 3586713 | ❌ Not recommended | — | — |
| Rev 084.00 | 3578258 | ❌ Not recommended | — | — |
| Rev 083.00 | 3550977 | ❌ Not recommended | Yes | No |
| Rev 082.00 | 3546799 | ❌ Not recommended | — | — |
| Rev 081.00 | 3542322 | ❌ Not recommended | — | Not recommended per SAP Note 2655761 (S/4HANA restrictions) |
| Rev 080.00 | 3531605 | ❌ Not recommended | — | ⚠️ Hotnews released for SPS08 |

---

## HANA 2.0 SPS07 Revision Status

| Revision | SAP Note | ECS Status | Notes |
|---|---|---|---|
| **Rev 079.10** | 3735239 | — | — |
| **Rev 079.09** ← **N-1 (Current)** | 3698808 | ✅ Available for ECS Customers | ⚠️ Security: SAP Note 3691059 [CVE-2026-0492] — privilege escalation vulnerability |
| Rev 079.08 | 3666954 | Available for ECS from target date | — |
| Rev 079.07 | 3645032 | — | Yes |
| Rev 079.06 | 3614625 | ❌ Not recommended | — |
| Rev 079.05 | 3590219 | ❌ Not recommended | Yes |
| Rev 079.04 | 3569218 | ❌ Not recommended | — |
| Rev 079.03 | 3549935 | ❌ Not recommended | — |
| Rev 079.02 | 3523457 | ❌ Not recommended | Yes / No |
| Rev 079.01 | 3495932 | ❌ Not recommended | Not recommended per SAP Note 2655761 |
| Rev 079.00 | 3470932 | ❌ Not recommended | — |

---

## Upgrade Path

- Upgrade from **Rev 079.09 → Rev 089.03** is **supported**
- ⚠️ Some revisions of a lower SPS are **not allowed** to upgrade to a higher SPS revision directly — refer to SAP Note **1948334** for compatibility matrix
- Revisions **079.05** and **087.00** will be **removed** and cannot be selected for updates or new builds

---

## Key References

| SAP Note | Description |
|---|---|
| 2196476 | Standard Database software releases in SAP ECS |
| 2378962 | SAP HANA 2.0 Revision and Maintenance Strategy |
| 2655761 | S/4HANA restrictions for specific HANA revisions |
| 1948334 | SAP HANA Database Update Paths |
| 3691059 | [CVE-2026-0492] Privilege escalation in SPS07 |

---

## Tools

- **Release Insights Pro (AI-powered):** Available for TSM, CDM, CAA, Launch Advisors, EOS, CAE T&A, PC3, CAE SE — saves 30-40% research time
- Wiki: ECS Database Release Management Dashboard | HANA Revision Validation Scope
