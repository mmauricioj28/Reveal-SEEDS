\# FMCSA Crash Record Reconciliation



\## Overview



This analysis investigates the difference between monthly crash totals

and carrier-year crash totals in the integrated FMCSA dataset.



Source files:

\- integration\_validation.json

\- quality.json



Integration output directory:

outputs/full\_integration\_20261024/



\## 1. Crash Record Counts



| Metric | Records |

|---|---:|

| Original crash records | 5,006,279 |

| Excluded outside analysis window | 3,137,882 |

| Retained crash records | 1,868,397 |

| Retained unidentified records | 401,528 |

| Retained linkable records | 1,466,869 |



\## 2. Reconciliation



Original records:

5,006,279 - 3,137,882 = 1,868,397



Retained records:

401,528 + 1,466,869 = 1,868,397



Both calculations reconcile exactly.



\## 3. Explanation of the Discrepancy



Monthly crash summaries contain all 1,868,397 retained records,

including records without usable carrier identifiers.



Carrier-year integration contains 1,466,869 linkable crash records.



The difference of 401,528 records represents retained crash records

without usable carrier identifiers.



These unidentified records account for approximately 21.5% of

retained crash records.



This difference is consistent with the integration pipeline's

documented validation logic and is not evidence of a failed

integration check.



\## 4. Census Matching



Of the 1,466,869 linkable crash records:



\- 1,445,772 are associated with carriers matched to Census.

\- 21,097 are associated with carriers unmatched to Census.



Unmatched records are different from unidentified records.



Unmatched records have usable carrier identifiers but do not

match a carrier in the Census dataset.



\## 5. Data Quality Implications



Monthly crash totals and carrier-year crash totals should not

be treated as interchangeable.



Monthly summaries include unidentified crash records, while

carrier-year summaries require usable carrier identifiers.



Carrier-level analyses therefore exclude approximately 21.5%

of retained crash records.



This missing linkage should be considered when interpreting

carrier-level crash patterns.



The analysis does not establish whether unidentified records

are systematically different from linkable records.



\## 6. Validation Status



The integration pipeline reported:



checks\_passed = true



The reported crash counts reconcile successfully.



\## 7. Recommended Next Steps



1\. Document the difference in record inclusion rules.

2\. Examine whether unidentified records vary by year or state.

3\. Assess whether excluding unidentified records could affect

&#x20;  interpretations of carrier-level crash trends.

4\. Share the findings with the Reveal research team.



\## Conclusion



The 401,528-record difference between monthly and carrier-year

crash totals is explained by retained records without usable

carrier identifiers.



This finding highlights an important limitation of carrier-level

analyses using the integrated FMCSA dataset.

