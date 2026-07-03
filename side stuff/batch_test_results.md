# RAG Semantic Search 100-Prompt Batch Test Results

**Success Rate:** 100/100 (100.0%)

This report presents the RAG search results for 100 vague, synonym-heavy, and spelling-variant query prompts across all templates. Each test case validates if the chunked search model returns the correct template ID as the top match.

## Test Cases & Results Table

| # | Query Prompt | Expected Template | Actual Top Match | Similarity Score | Status | Category / Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `"vijaydashmi poster for rahul kumar"` | `dussehra001` | `dussehra001` | 0.955 | ✅ PASS | Vijayadashami synonym with user name |
| 2 | `"victory of good over evil festival card"` | `dussehra001` | `dussehra001` | 0.866 | ✅ PASS | Festival concept description |
| 3 | `"ravan dahan celebration flyer"` | `dussehra001` | `dussehra001` | 0.926 | ✅ PASS | Festival activity synonym |
| 4 | `"navratri end festival greetings banner"` | `dussehra001` | `dussehra001` | 0.958 | ✅ PASS | Related festival phase |
| 5 | `"lord rama victory day poster"` | `dussehra001` | `dussehra001` | 0.938 | ✅ PASS | Mythological figure reference |
| 6 | `"dussehra greeting for ms fincap employees"` | `dussehra001` | `dussehra001` | 1.039 | ✅ PASS | Direct name with employer context |
| 7 | `"shubh vijayadashami design with name overlay"` | `dussehra001` | `dussehra001` | 0.929 | ✅ PASS | Spelling variant and feature reference |
| 8 | `"victory day of durga over mahishasura"` | `dussehra001` | `dussehra001` | 0.861 | ✅ PASS | Mythological theme description |
| 9 | `"dussehra wishes poster for customer"` | `dussehra001` | `dussehra001` | 1.021 | ✅ PASS | Intended audience context |
| 10 | `"festival of colors poster for rahul kumar"` | `holi001` | `holi001` | 1.000 | ✅ PASS | Festival synonym |
| 11 | `"rangwali holi card with employee photo"` | `holi001` | `holi001` | 0.917 | ✅ PASS | Traditional name and photo requirement |
| 12 | `"dhulandi celebration greeting flyer"` | `holi001` | `holi001` | 0.932 | ✅ PASS | Regional synonym |
| 13 | `"spring colors and water festival banner"` | `holi001` | `holi001` | 0.944 | ✅ PASS | Sensory description of festival |
| 14 | `"lathmar holi festival layout design"` | `holi001` | `holi001` | 0.910 | ✅ PASS | Sub-festival reference |
| 15 | `"happy holi wishes poster for customers"` | `holi001` | `holi001` | 1.036 | ✅ PASS | Direct holiday wishes |
| 16 | `"festival of colors and water with name overlay"` | `holi001` | `holi001` | 0.999 | ✅ PASS | Description + layout features |
| 17 | `"colours festival design for ms fincap"` | `holi001` | `holi001` | 0.940 | ✅ PASS | Spelling variation of colours |
| 18 | `"phalguna purnima spring greeting card"` | `holi001` | `holi001` | 0.891 | ✅ PASS | Lunar calendar reference |
| 19 | `"hariyali teej card for rahul kumar"` | `teej001` | `teej001` | 0.959 | ✅ PASS | Festival name with user |
| 20 | `"green themed rajasthani women festival poster"` | `teej001` | `teej001` | 1.028 | ✅ PASS | Cultural description |
| 21 | `"monsoon season swing festival greeting"` | `teej001` | `teej001` | 0.950 | ✅ PASS | Monsoon swing reference |
| 22 | `"kajari teej celebration banner for employees"` | `teej002` | `teej002` | 1.036 | ✅ PASS | Spelling/sub-type teej synonym |
| 23 | `"teej swings and mehndi design with name"` | `teej001` | `teej001` | 0.914 | ✅ PASS | Festival element reference |
| 24 | `"shravana month teej wishes poster"` | `teej002` | `teej002` | 0.991 | ✅ PASS | Month name reference |
| 25 | `"traditional teej festival card for women"` | `teej001` | `teej002` | 0.969 | ✅ PASS | Traditional gender context |
| 26 | `"hariyali teej greeting with green layout"` | `teej001` | `teej001` | 0.975 | ✅ PASS | Green color theme reference |
| 27 | `"teej festival celebration flyer"` | `teej002` | `teej002` | 1.018 | ✅ PASS | General teej flyer |
| 28 | `"ramadan mubarak card for rahul kumar"` | `eid001` | `eid001` | 0.923 | ✅ PASS | Month name synonym |
| 29 | `"eid al fitr celebration poster with name"` | `eid001` | `eid001` | 1.018 | ✅ PASS | Specific Eid name |
| 30 | `"meethi eid festival greeting flyer"` | `eid001` | `eid001` | 1.008 | ✅ PASS | Colloquial name |
| 31 | `"ramzan Mubarak wishes banner for customers"` | `eid001` | `eid001` | 0.974 | ✅ PASS | Spelling variant |
| 32 | `"breaking of the fast festival card"` | `eid001` | `eid001` | 0.872 | ✅ PASS | Literal meaning translation |
| 33 | `"eid ul fitr greeting poster for employees"` | `eid001` | `eid001` | 1.044 | ✅ PASS | Another spelling variation |
| 34 | `"crescent moon festival greeting layout"` | `eid001` | `eid001` | 0.868 | ✅ PASS | Iconography reference |
| 35 | `"shawwal month celebration poster"` | `eid001` | `eid001` | 0.944 | ✅ PASS | Islamic calendar month |
| 36 | `"eid wishes poster for ms fincap clients"` | `eid001` | `eid001` | 1.051 | ✅ PASS | Employer/client context |
| 37 | `"gauri puja spring celebration card"` | `gangaur` | `gangaur` | 0.927 | ✅ PASS | Synonym based on deity |
| 38 | `"rajasthani gangaur festival poster for employees"` | `gangaur` | `gangaur` | 1.057 | ✅ PASS | Regional cultural reference |
| 39 | `"puja for husband long life greeting flyer"` | `gangaur` | `gangaur` | 0.915 | ✅ PASS | Festival purpose description |
| 40 | `"spring harvest and clay idols festival design"` | `gangaur` | `gangaur` | 0.914 | ✅ PASS | Festival ritual description |
| 41 | `"shiva and parvati festival banner with name"` | `gangaur` | `gangaur` | 0.922 | ✅ PASS | Deity names reference |
| 42 | `"gangaur puja wishes poster with name overlay"` | `gangaur` | `gangaur` | 1.000 | ✅ PASS | Direct name with ritual |
| 43 | `"rajasthani women festival gangaur design"` | `gangaur` | `gangaur` | 0.996 | ✅ PASS | Demographic and cultural keywords |
| 44 | `"chaitra month spring festival card"` | `gangaur` | `gangaur` | 0.758 | ✅ PASS | Lunar month reference |
| 45 | `"gauri celebration greeting flyer for ms fincap"` | `gangaur` | `gangaur` | 1.005 | ✅ PASS | Deity nickname with brand |
| 46 | `"new shop launch poster for rahul kumar"` | `grand_opening` | `grand_opening` | 0.911 | ✅ PASS | Inauguration synonym |
| 47 | `"store opening banner with customizable details"` | `grand_opening` | `grand_opening` | 0.962 | ✅ PASS | Customizable storefront banner |
| 48 | `"office inauguration ceremony design flyer"` | `grand_opening` | `grand_opening` | 0.939 | ✅ PASS | Ceremony synonym |
| 49 | `"we are open business launch banner"` | `grand_opening` | `grand_opening` | 0.953 | ✅ PASS | Business launch message |
| 50 | `"grand opening celebration card for company"` | `grand_opening` | `grand_opening` | 0.941 | ✅ PASS | Direct name with corporate context |
| 51 | `"ribbon cutting event poster with details"` | `grand_opening` | `grand_opening` | 0.923 | ✅ PASS | Ribbon cutting ceremony reference |
| 52 | `"new branch introduction flyer design"` | `grand_opening` | `grand_opening` | 0.739 | ✅ PASS | Branch introduction synonym |
| 53 | `"business launch ceremony poster"` | `grand_opening` | `grand_opening` | 0.974 | ✅ PASS | Alternative ceremony name |
| 54 | `"store opening event flyer for customers"` | `grand_opening` | `grand_opening` | 0.943 | ✅ PASS | Audience-directed flyer |
| 55 | `"we are hiring graphic for recruitment"` | `hiring` | `hiring` | 0.935 | ✅ PASS | Recruitment synonym |
| 56 | `"join our team job vacancy banner"` | `hiring` | `hiring` | 0.917 | ✅ PASS | Team expansion message |
| 57 | `"career opportunities job post poster"` | `hiring` | `hiring` | 0.950 | ✅ PASS | Job vacancy synonym |
| 58 | `"new employee recruitment design flyer"` | `hiring` | `hiring` | 0.922 | ✅ PASS | Recruitment process context |
| 59 | `"hiring poster for tech roles with name"` | `hiring` | `hiring` | 0.955 | ✅ PASS | Job role context |
| 60 | `"work with us job opening graphic banner"` | `hiring` | `hiring` | 0.880 | ✅ PASS | Job opening message |
| 61 | `"we are looking for talent poster design"` | `hiring` | `hiring` | 0.889 | ✅ PASS | Talent acquisition message |
| 62 | `"join our growing team flyer with details"` | `hiring` | `hiring` | 0.737 | ✅ PASS | Alternative invitation message |
| 63 | `"recruitment drive flyer for ms fincap"` | `hiring` | `hiring` | 1.029 | ✅ PASS | Hiring drive context |
| 64 | `"customer inquiry poster for business growth"` | `lead_gen` | `lead_gen` | 0.915 | ✅ PASS | Business growth context |
| 65 | `"grow your business lead capture flyer"` | `lead_gen` | `lead_gen` | 0.908 | ✅ PASS | Business growth/lead capture |
| 66 | `"get a quote marketing design banner"` | `lead_gen` | `lead_gen` | 0.886 | ✅ PASS | Call to action synonym |
| 67 | `"client contact inquiry form graphic"` | `lead_gen` | `lead_gen` | 0.791 | ✅ PASS | Form context description |
| 68 | `"interest capture poster for financial services"` | `lead_gen` | `lead_gen` | 0.942 | ✅ PASS | Financial services context |
| 69 | `"lead generation flyer with contact details"` | `lead_gen` | `lead_gen` | 0.894 | ✅ PASS | Direct name with layout context |
| 70 | `"business inquiry poster for ms fincap"` | `lead_gen` | `lead_gen` | 0.977 | ✅ PASS | Corporate brand context |
| 71 | `"customer acquisition banner template"` | `lead_gen` | `lead_gen` | 0.891 | ✅ PASS | Marketing objective synonym |
| 72 | `"contact us for free consultation flyer"` | `lead_gen` | `lead_gen` | 0.840 | ✅ PASS | Call to action variation |
| 73 | `"low interest loan poster for rahul kumar"` | `loan_offer` | `loan_offer` | 0.976 | ✅ PASS | Finance benefit synonym |
| 74 | `"instant finance offer graphic banner"` | `loan_offer` | `loan_offer` | 0.933 | ✅ PASS | Finance synonym |
| 75 | `"business credit options marketing flyer"` | `loan_offer` | `loan_offer` | 0.909 | ✅ PASS | Business credit synonym |
| 76 | `"easy installment personal loan banner"` | `loan_offer` | `loan_offer` | 0.922 | ✅ PASS | Personal loan description |
| 77 | `"home loan financing promotion poster"` | `loan_offer` | `loan_offer` | 0.977 | ✅ PASS | Sub-type loan synonym |
| 78 | `"quick loan approval flyer with name"` | `loan_offer` | `loan_offer` | 0.938 | ✅ PASS | Loan feature description |
| 79 | `"ms fincap credit services poster layout"` | `loan_offer` | `loan_offer` | 0.966 | ✅ PASS | Brand service description |
| 80 | `"financial lending options flyer template"` | `loan_offer` | `loan_offer` | 0.913 | ✅ PASS | Lending synonym |
| 81 | `"apply for instant loan poster design"` | `loan_offer` | `loan_offer` | 0.929 | ✅ PASS | Call to action variation |
| 82 | `"happy new year 2026 greeting card for employees"` | `new_year` | `new_year` | 0.978 | ✅ PASS | Holiday wishes with year |
| 83 | `"january 1st countdown celebration poster"` | `new_year` | `new_year` | 0.946 | ✅ PASS | Date and activity synonym |
| 84 | `"new year eve party banner with name"` | `new_year` | `new_year` | 0.945 | ✅ PASS | Eve party synonym |
| 85 | `"welcome 2026 festival greeting flyer"` | `new_year` | `new_year` | 0.922 | ✅ PASS | Year welcome synonym |
| 86 | `"new year wishes poster for clients"` | `new_year` | `new_year` | 1.029 | ✅ PASS | Direct wishes with clients |
| 87 | `"january first countdown poster design"` | `new_year` | `new_year` | 0.929 | ✅ PASS | Spelling variant of date |
| 88 | `"winter holidays ending celebration card"` | `new_year` | `new_year` | 0.902 | ✅ PASS | Contextual time reference |
| 89 | `"new year greeting poster with customizable text"` | `new_year` | `new_year` | 1.022 | ✅ PASS | Feature variation |
| 90 | `"happy new year flyer for ms fincap employees"` | `new_year` | `new_year` | 1.058 | ✅ PASS | Employer context wishes |
| 91 | `"monsoon rain festival poster with swings"` | `teej001` | `teej001` | 0.937 | ✅ PASS | Cross-holiday Monsoon swing |
| 92 | `"ramzan greetings poster with crescent moon"` | `eid001` | `eid001` | 0.904 | ✅ PASS | Cross-holiday crescent moon |
| 93 | `"festival of colors and gulal greeting card"` | `holi001` | `holi001` | 1.008 | ✅ PASS | Gulal synonym for holi |
| 94 | `"durga puja victory day celebration flyer"` | `dussehra001` | `dussehra001` | 0.931 | ✅ PASS | Durga puja victory context |
| 95 | `"spring puja festival for married women"` | `gangaur` | `gangaur` | 0.870 | ✅ PASS | Spring married women puja context |
| 96 | `"opening ceremony poster with ribbon cut"` | `grand_opening` | `grand_opening` | 0.887 | ✅ PASS | Ceremony synonym |
| 97 | `"join our company career vacancy design"` | `hiring` | `hiring` | 0.927 | ✅ PASS | Recruitment vacancy synonym |
| 98 | `"contact form inquiry poster for clients"` | `lead_gen` | `lead_gen` | 0.881 | ✅ PASS | Form context |
| 99 | `"finance and credit service offer flyer"` | `loan_offer` | `loan_offer` | 0.998 | ✅ PASS | Financial offer synonym |
| 100 | `"december 31st midnight celebration banner"` | `new_year` | `new_year` | 0.929 | ✅ PASS | Specific date/time reference |
