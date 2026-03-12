# Portfolio Taxonomy: Complete Dimensions & Values Reference

## Overview

This reference defines every dimension and its allowed values for tagging portfolio holdings. Each holding receives one value per dimension. Reports can then aggregate along any axis — asset class, objective, region, style, credit quality, duration, factor, liquidity, vehicle type, income type, or account tax treatment — giving a multi-faceted view of portfolio composition.

The taxonomy is designed for a near-retirement, income-oriented investor with holdings spanning domestic and international equities, bonds, alternatives, and cash.

***

## Dimension 1 — Asset Class

The top-level classification that groups holdings by the fundamental type of asset.[^1][^2]

| Value | Description / What Goes Here |
|---|---|
| **US Equity** | US-domiciled stocks, US stock index ETFs/funds (e.g., VTI, SPY, individual US stocks)[^3] |
| **Intl Developed Equity** | Developed-market ex-US stocks and funds (e.g., VXUS developed portion, EFA)[^3][^4] |
| **Emerging Market Equity** | EM stocks and funds (e.g., VWO, IEMG)[^3][^4] |
| **Investment-Grade Bond** | Govt, agency, and IG corporate bonds/funds rated BBB−/Baa3 or above (e.g., BND, AGG)[^5][^6] |
| **High-Yield Bond** | Below-IG corporate bonds and funds rated BB+ or lower (e.g., HYG, JNK)[^5][^6] |
| **Intl / EM Bond** | Non-US sovereign and corporate bonds/funds (e.g., BNDX, EMB)[^3] |
| **TIPS / Inflation-Linked** | Treasury Inflation-Protected Securities and similar funds (e.g., TIP, SCHP)[^7] |
| **Cash & Equivalents** | Money market, T-bills, stable value, CDs, HYSA[^1][^2] |
| **Real Estate (REITs)** | Publicly traded REITs and real-estate funds (e.g., VNQ, SCHH)[^8][^9] |
| **Commodities** | Gold, silver, energy, agriculture, broad commodity ETFs (e.g., GLD, PDBC)[^10][^11] |
| **Infrastructure** | Listed infrastructure funds and utilities-focused vehicles (e.g., PAVE, IGF)[^12][^10] |
| **Private Credit / BDC** | Business Development Companies and private lending vehicles (e.g., ARCC, MAIN)[^13][^14] |
| **MLP / Energy Income** | Master Limited Partnerships and midstream energy vehicles (e.g., AMLP, EPD)[^13] |
| **Preferred Stock** | Preferred shares and preferred ETFs (e.g., PFF, PGX)[^13] |
| **Multi-Asset / Allocation** | Target-date or balanced funds that blend multiple asset classes internally[^3] |
| **Other Alternative** | Hedge fund strategies, option-overlay, managed futures, volatility, collectibles, crypto[^1][^14] |

***

## Dimension 2 — Investment Objective

Classifies each holding by its primary purpose in the portfolio.[^15][^16]

| Value | Description |
|---|---|
| **Growth** | Holdings targeting capital appreciation with little or no current income (e.g., growth-stock ETFs, EM equity)[^17][^15] |
| **Income** | Holdings whose primary role is generating regular cash distributions (e.g., dividend ETFs, bond funds, BDCs, MLPs, covered-call funds like SPYI, CEFs)[^17][^16][^18] |
| **Preservation** | Holdings prioritizing capital safety and liquidity over return (e.g., T-bills, stable value, short-duration IG bonds, money market)[^16][^15] |
| **Growth & Income** | Holdings that blend meaningful appreciation with meaningful yield (e.g., dividend-growth funds, equity-income, balanced funds)[^17][^15] |

***

## Dimension 3 — Geographic Region

Where the underlying assets are domiciled or derive revenue.[^4][^19]

| Value | Description |
|---|---|
| **US** | United States[^4] |
| **Developed ex-US** | Canada, Western Europe, Japan, Australia, etc. (MSCI World ex-US constituents)[^4] |
| **Emerging Markets** | China, India, Brazil, Taiwan, South Korea, etc. (MSCI EM constituents)[^4] |
| **Frontier** | Smaller markets (Vietnam, Nigeria, Bangladesh, etc.)[^4] |
| **Global** | Funds that span all regions without a single-region tilt (e.g., ACWI, global bond fund)[^4] |

***

## Dimension 4 — Equity Style (Morningstar Style Box)

A 3×3 grid combining market capitalization and valuation style. Apply only to equity holdings; leave blank for bonds/cash/alts.[^20][^21][^22]

**Cap axis:**

| Value | Description |
|---|---|
| **Large Cap** | Companies in the top 70% of market cap[^22][^21] |
| **Mid Cap** | Next 20% of market cap[^22][^21] |
| **Small Cap** | Bottom 10% of market cap[^22][^21] |

**Style axis:**

| Value | Description |
|---|---|
| **Value** | Low P/E, P/B, and high dividend yield relative to peers[^22][^20] |
| **Blend / Core** | Mix of value and growth characteristics[^22][^20] |
| **Growth** | High earnings growth, high P/E, low or no dividend yield[^22][^20] |

Combined, this yields 9 cells: Large Value, Large Blend, Large Growth, Mid Value, Mid Blend, Mid Growth, Small Value, Small Blend, Small Growth.[^21][^22]

***

## Dimension 5 — Fixed-Income Style (Morningstar FI Style Box)

A 3×3 grid combining interest-rate sensitivity and credit quality. Apply only to bond/fixed-income holdings.[^23][^24][^25]

**Interest-Rate Sensitivity (Duration):**

| Value | Effective Duration | Description |
|---|---|---|
| **Limited** | ≤ 3.5 years | Short-duration; least price-sensitive to rate changes[^23][^26] |
| **Moderate** | 3.5–6.0 years | Intermediate; core bond territory[^23][^26] |
| **Extensive** | > 6.0 years | Long-duration; most price-sensitive[^23][^26] |

**Credit Quality:**

| Value | Rating Range | Description |
|---|---|---|
| **High** | AAA to A− | Government, agency, high-quality corporate[^23][^6] |
| **Medium** | BBB+ to BBB− | Lower investment-grade corporate[^23][^6] |
| **Low** | BB+ and below | High-yield / speculative / junk[^23][^5] |

Combined, this yields 9 cells (e.g., High/Limited, Medium/Moderate, Low/Extensive).[^25][^23]

***

## Dimension 6 — Fixed-Income Sector

The type of bond issuer or structure. Apply only to bond holdings.[^27][^7]

| Value | Description |
|---|---|
| **Government / Sovereign** | US Treasuries, foreign government bonds[^7] |
| **Agency / GSE** | Fannie Mae, Freddie Mac, Ginnie Mae[^27] |
| **Investment-Grade Corporate** | BBB− or above corporate issuers[^6][^5] |
| **High-Yield Corporate** | Below BBB− corporate issuers[^6][^5] |
| **Securitized (MBS/ABS/CMBS)** | Mortgage-backed, asset-backed, commercial MBS[^27] |
| **Municipal (Tax-Exempt)** | State and local government obligations[^3][^28] |
| **Bank Loans / Floating Rate** | Senior secured floating-rate loans (e.g., BKLN)[^13] |
| **TIPS / Inflation-Linked** | Inflation-protected government securities[^7] |
| **Intl / EM Sovereign** | Non-US government debt[^3] |
| **Preferred / Hybrid** | Preferred securities and convertible bonds[^13] |

***

## Dimension 7 — Factor Exposure

Captures the dominant return-driving factor(s) of the holding, per academic factor-investing research.[^29][^30][^31]

| Value | Description |
|---|---|
| **Value** | Targets stocks trading at discounts to fundamentals (low P/E, P/B)[^29][^30] |
| **Growth** | Targets stocks with above-average earnings/revenue growth[^32][^30] |
| **Quality** | Targets firms with high ROE, stable earnings, low leverage[^29][^32] |
| **Momentum** | Targets stocks with strong recent price performance[^29][^30] |
| **Low Volatility / Min Vol** | Targets stocks with lower price variability than the market[^30][^33] |
| **High Yield / Dividend** | Targets above-average dividend-paying stocks[^31][^33] |
| **Size (Small Cap)** | Targets small-cap premium[^29][^31] |
| **Broad / Market-Weight** | No deliberate factor tilt (e.g., total-market index)[^32] |
| **N/A** | Non-equity holdings where equity factors don't apply |

***

## Dimension 8 — Income Type

How the holding generates cash distributions, important for tax planning and retirement income forecasting.[^34][^35]

| Value | Description |
|---|---|
| **Qualified Dividends** | Dividends eligible for lower capital-gains tax rates (most US and some foreign stocks)[^28][^35] |
| **Non-Qualified Dividends** | Ordinary-rate dividends (REITs, some foreign stocks, BDCs)[^28] |
| **Interest / Coupon** | Bond interest, CD interest, money-market income — taxed as ordinary income[^34][^35] |
| **Tax-Exempt Interest** | Municipal bond interest exempt from federal (and possibly state) tax[^28] |
| **Return of Capital** | Distributions that reduce cost basis rather than being immediately taxable (common in MLPs, some CEFs)[^13] |
| **Capital Gains Distributions** | Mutual fund / ETF capital gains pass-throughs[^35][^36] |
| **Option Premium / Synthetic** | Income from covered-call or option-overlay strategies (e.g., SPYI)[^18] |
| **No Current Income** | Growth-only holdings with no distributions |

***

## Dimension 9 — Liquidity

How quickly the position can be converted to cash at fair value.[^8][^1]

| Value | Description |
|---|---|
| **Daily Liquid** | Trades on an exchange intraday at or near NAV (individual stocks, ETFs, CEFs)[^1][^37] |
| **Daily at NAV** | Open-end mutual funds priced once per day[^38][^39] |
| **Interval / Semi-Liquid** | Interval funds, non-traded REITs with periodic redemption windows[^1] |
| **Illiquid** | Private equity, private real estate, lock-up hedge funds — no regular redemption[^1][^14] |

***

## Dimension 10 — Vehicle Type

The legal / structural wrapper of the investment.[^37][^38][^39]

| Value | Description |
|---|---|
| **Individual Stock** | Single equity security[^39] |
| **Individual Bond** | Single fixed-income security (Treasury, corporate, muni)[^39] |
| **ETF** | Exchange-traded fund — intraday trading, flexible share count[^38][^37] |
| **Open-End Mutual Fund** | Mutual fund priced at end-of-day NAV[^38][^39] |
| **Closed-End Fund (CEF)** | Fixed share count, trades at premium/discount to NAV[^37][^40] |
| **Money Market Fund** | Stable NAV fund holding short-term instruments[^1] |
| **CD / Savings** | Certificates of deposit, high-yield savings accounts[^41] |
| **LP / Partnership** | MLPs and other limited partnerships[^13] |
| **Annuity** | Insurance-wrapped investment contract |
| **Other** | Crypto, options positions, private placements |

***

## Dimension 11 — Account Tax Treatment

The tax wrapper where the holding is located — critical for asset-location optimization.[^41][^42][^43]

| Value | Description |
|---|---|
| **Taxable** | Brokerage account; gains, dividends, and interest taxed annually[^41][^43] |
| **Tax-Deferred** | Traditional IRA, 401(k), 403(b); contributions pre-tax, withdrawals taxed as ordinary income[^41][^42] |
| **Tax-Exempt** | Roth IRA, Roth 401(k); contributions post-tax, qualified withdrawals tax-free[^41][^42] |
| **HSA** | Health Savings Account; triple-tax-advantaged (pre-tax in, tax-free growth, tax-free out for medical)[^41] |

***

## How the Dimensions Work Together

Each holding gets tagged with one value per dimension. A single position might look like:

| Dimension | Example: SPYI | Example: BND | Example: ARCC |
|---|---|---|---|
| Asset Class | US Equity | Investment-Grade Bond | Private Credit / BDC |
| Objective | Income | Preservation | Income |
| Region | US | US | US |
| Equity Style | Large Blend | — | — |
| FI Style | — | High / Moderate | — |
| FI Sector | — | Govt + IG Corp blend | Bank Loans |
| Factor | High Yield / Dividend | N/A | N/A |
| Income Type | Option Premium / Synthetic | Interest / Coupon | Non-Qualified Dividends |
| Liquidity | Daily Liquid | Daily Liquid | Daily Liquid |
| Vehicle Type | ETF | ETF | Individual Stock |
| Account Tax Treatment | (depends on where held) | (depends on where held) | (depends on where held) |

This multi-dimensional tagging enables reports such as:

- **% Growth vs. Income vs. Preservation** — tracks alignment with retirement income targets
- **Forward portfolio yield by objective** — validates the 7–8% income target[^13]
- **Factor tilt summary** — reveals hidden style concentrations[^33][^29]
- **Asset-location efficiency** — flags tax-inefficient holdings in taxable accounts (e.g., BDCs, HY bonds) that should migrate to tax-deferred/exempt[^43][^44]
- **Liquidity profile** — ensures sufficient daily-liquid assets for near-term retirement cash needs[^1]

---

## References

1. [Asset Classes: List, Characteristics, Asset Allocation - Macroption](https://www.macroption.com/asset-classes/)

2. [Asset classes explained: Cash, bonds, real assets and equities](https://www.usbank.com/investing/financial-perspectives/investing-insights/asset-classes-explained.html) - An asset class is a grouping of investments that have similar characteristics. ... Each asset class ...

3. [Asset Class | Investing Terms and Definitions - Morningstar](https://www.morningstar.com/investing-terms/asset-class) - Asset class is a term used to group funds and ETFs with similar categories and investing styles. The...

4. [Taxonomies - Portfolio Performance Manual](https://help.portfolio-performance.info/en/reference/view/taxonomies/) - Manual of Portfolio Performance

5. [[PDF] Fixed Income Securities Fixed Income Markets: Issuance, Trading ...](https://mentormecareers.com/wp-content/uploads/2024/01/Reading-40-Fixed-Income-Markets-Issuance-trading-and-Funding.pdf)

6. [[PDF] Fixed Income Investing](https://www.fidelity.com/bin-public/060_www_fidelity_com/documents/managed-accounts/Fixed-Income-Investing.pdf)

7. [[PDF] Overview of Asset Class Definitions (New) - NDPERS](https://www.ndpers.nd.gov/sites/www/files/documents/about/investments/asset-class-definitions-aug-2014.pdf)

8. [Types of investing assets | Asset classes - Fidelity Investments](https://www.fidelity.com/learning-center/trading-investing/types-of-investments) - From stocks and bonds to alternatives, you have a lot of investing choices.

9. [Different Asset Classes | BlackRock](https://www.blackrock.com/americas-offshore/en/education/alternative-asset-classes-part-2) - Explore Module 3: Learn about what each alternative asset class entails across hedge funds, private ...

10. [10 Types of Alternative Investment in Modern Portfolios](https://www.straitsfinancial.com/insights/types-of-alternative-investment) - A breakdown of key alternative investment types, examples, and why alternative investments matter fo...

11. [7 Types of Alternative Investments Everyone Should Know](https://online.hbs.edu/blog/post/types-of-alternative-investments) - Here are 7 types of alternative investments you should know to maximize the value of your portfolio ...

12. [Asset classes - Wikipedia](https://en.wikipedia.org/wiki/Asset_classes)

13. [I would like to consider additional emphasis on corporate bonds that are a bit below investment grade.  I would like to consider MLPs and BDCs to get my overall portfolio income to around 7% to 8%.  What would you recommend?](https://www.perplexity.ai/search/402d8a40-ea7c-4b93-824e-239992e13c1e) - Based on your goal to achieve 7-8% portfolio income through high-yield corporate bonds below investm...

14. [What are the Different Types of...](https://www.wallstreetprep.com/knowledge/alternative-investments/) - Alternative Investments are comprised of non-traditional asset classes, such as private equity, hedg...

15. [How to Choose Investment Objectives for Your Portfolio - SmartAsset](https://smartasset.com/investing/investing-objectives) - Consider whether you're aiming for growth, steady income, or preserving capital, as each objective a...

16. [3 Key Investment Goals: Growth, Income and Stability](https://www.fbfs.com/learning-center/3-key-investment-goals-growth-income-and-stability) - Growth, income and stability are all related when it comes to your investments. A stronger emphasis ...

17. [Income vs growth investing: The key differences](https://www.personalinvesting.jpmorgan.com/insights/income-vs-growth-investment-portfolios) - Investing for growth focuses on increasing portfolio value, while investing for income prioritises p...

18. [Evaluate SPYI as an investment vs SPY.  I would like to be able to capture some SPY upside if it goes up from here, but I would like less risk in my portfolio.  I am also interested in income.  Does SPYI support these requirements?](https://www.perplexity.ai/search/18c98eba-5e63-43ba-8f3d-2e59f4aff038) - SPYI (NEOS S&P 500 High Income ETF) provides higher income with lower volatility compared to SPY, bu...

19. [Dimensional's Approach to Asset Allocation](https://www.dimensional.com/ca-en/insights/dimensionals-approach-to-asset-allocation) - Dimensional applies robust investment principles to asset allocation. Our approach starts with defin...

20. [Explained: What is investment style box in mutual funds and what it ...](https://economictimes.com/mf/analysis/explained-what-is-investment-style-box-in-mutual-funds-and-what-it-means-for-investors/articleshow/123599725.cms) - It helps investors assess strategy, diversification, and risk by showing whether a fund leans toward...

21. [Analyzing Funds Using the Morningstar Style Box™ | HFG Trust](https://hfgtrust.com/analyzing-funds-using-the-morningstar-style-box/) - The box is divided into nine squares, representing the intersection of the three market cap categori...

22. [Style Boxes Explained: Parameters and Investment Limitations](https://www.investopedia.com/terms/s/stylebox.asp) - Morningstar's style box uses a 3x3 grid to differentiate between value, growth, and blend (or core) ...

23. [Morningstar Fixed-Income Style BoxTM](https://www.morningstar.com/content/dam/marketing/shared/research/foundational/Fixed-Income-Style-Box-Methodology-Paper.pdf)

24. [[PDF] Morningstar Fixed-Income Style Box Methodology Enhancement](https://advisor.morningstar.com/Enterprise/VTC/FISBFAQ.pdf)

25. [Morningstar Fixed Income Style Box Methodology](https://www.morningstar.com.au/investing/morningstar-fixed-income-style-box-methodology) - The model for the fixed income style box is based on the two pillars of fixed-income performance: in...

26. [?](https://advisor.morningstar.com/enterprise/vtc/MorningstarFixedIncomeStyleBoxMethodology.pdf)

27. [Optimizing Risk-Return Outcomes in Core Fixed Income](https://www.pnccapitaladvisors.com/insights/a-19/optimizing-risk-return-outcomes-in-core-fixed-income/) - Key observations we learned by examining our investment process versus our objective to optimize ris...

28. [Portfolio Income Tax Overview - TaxBuzz Guides](https://www.taxbuzz.com/guides/tax-income-issues/portfolio-income-tax-overview) - A comprehensive look at how the Internal Revenue Service (IRS) treats portfolio income in regard to ...

29. [Foundational concepts for understanding factor investing - Invesco](https://www.invesco.com/apac/en/institutional/insights/factor-investing/foundational-concepts-for-understanding-factor-investing.html) - Factor investing is a third pillar of investing, complementing active and passive approaches. We exp...

30. [Factor Investing Strategies for Fast-Moving Markets - iShares](https://www.ishares.com/us/insights/dynamic-factor-rotation-investing) - Explore factor investing strategies to optimize returns and manage risks. Learn how dynamic adjustme...

31. [[PDF] Foundations of Factor Investing - MSCI](https://www.msci.com/documents/1296102/1336482/Foundations_of_Factor_Investing.pdf)

32. [Multi-Factor Solutions](https://russellinvestments.com/content/ri/ca/en/financial-professional/investments/products/multi-factor-solutions.html) - Our multi-factor solutions offer a complement to any investing strategy, designed to harness increme...

33. [Paying Attention to Investment Factors? You Should Be](https://www.morningstar.com/personal-finance/paying-attention-investment-factors-you-should-be) - Delve into factors like value, momentum, and quality to unlock fresh perspectives on portfolio perfo...

34. [Investment income compared: dividends, interest and capital gains](https://www.rothenberg.ca/investment-income-compared/) - When building a portfolio that generates income, Canadian investors often weigh the benefits of divi...

35. [Portfolio Income: Definition, Examples, Ways To Increase](https://www.investopedia.com/terms/p/portfolioincome.asp) - Portfolio income is money received from investments, dividends, interest, and capital gains. It is o...

36. [Portfolio and Non-Taxable Income - How Is My Income Taxed?](https://www.taxsavingspodcast.com/blog/portfolio-income-how-is-my-income-taxed) - This could also be called "investment income". Per the IRS, this generally includes interest, divide...

37. [Exchange-Traded Funds (ETFs) vs. Closed-End Funds: What's the Difference?](https://www.investopedia.com/ask/answers/052615/what-difference-between-exchange-traded-funds-etfs-and-closed-end-funds.asp) - Understand the difference between exchange-traded funds and closed-end funds, and learn how investor...

38. [Stocks, bonds, mutual funds, and ETFs](https://us.etrade.com/knowledge/library/getting-started/common-investment-types) - There are various types of investment vehicles you can use within your portfolio. Learn what they ar...

39. [Investing in a stock, bond, ETF, or mutual fund | Vanguard](https://investor.vanguard.com/investor-resources-education/article/investing-in-a-stock-bond-etf-or-mutual-fund?msockid=38150a306718643001821c3a66f36547) - Learn more about some of the different investment products you can choose for your portfolio.

40. [Publicly Traded Investment Vehicles: Refresher comparing ETFs, Mutual Funds, and CEFs](https://www.infracapfunds.com/post/publicly-traded-investment-vehicles-refresher-on-difference-between-etfs-mutual-funds-and-cefs) - In this investing primer, we outline the differences and advantages of ETFs vs Mutual Funds and CEFs...

41. [Asset Strategies Using Taxable vs. Tax-Deferred - J. Martin Wealth](https://www.jmartinwm.com/blog/asset-location-strategies-using-taxable-tax-deferred-and-tax-exempt-accounts) - Maximize wealth with asset location strategies. Optimize your financial future using taxable, tax-de...

42. [Asset Location Strategies Using Taxable, Tax-Deferred, and Tax ...](https://trajanwealth.com/blog/asset-location-strategies/) - Knowing the difference between account strategies may improve portfolio diversification and how much...

43. [Asset Location: The Tax Strategy Hidden Inside Your Portfolio](https://www.wedbush.com/asset-location-the-tax-strategy-hidden-inside-your-portfolio/) - What you own matters — but so does where you own it. Discover how asset location can reduce tax drag...

44. [[PDF] Asset location in tax-deferred and conventional savings accounts](https://faculty.mccombs.utexas.edu/clemens.sialm/ssjpube.pdf)

