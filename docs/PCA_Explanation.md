# Why We Use Principal Component Analysis (PCA) to Construct the Area Deprivation Index

## The Simple Explanation

Imagine you want to know how "deprived" a county is. You have 6 different measurements:

1. How many people are in poverty
2. How many people are unemployed
3. How many people lack a high school diploma
4. How many households spend too much on housing
5. How low the median income is
6. How many children are in poverty

Each of these tells you *something* about deprivation, but none alone tells the whole story. You need a way to combine them into a single "deprivation score."

## Why Not Just Average Them?

Three problems with a simple average:

**Problem 1: Different scales.** Poverty is measured as a percentage (0% to 50%), but income is measured in dollars ($20,000 to $150,000). You cannot average a percentage and a dollar amount directly.

**Problem 2: Redundancy.** "Percent in poverty" and "percent of children in poverty" are highly correlated (r = 0.85). If you average them equally, you are double-counting the poverty signal while undercounting other aspects of deprivation.

**Problem 3: Equal weighting assumption.** A simple average assumes all 6 variables contribute equally. But what if unemployment varies little across counties while poverty varies a lot? The poverty variable actually carries more *information* about between-county differences, and should get more weight.

## What PCA Does (Step by Step)

### Step 1: Standardize

Convert all 6 variables to the same scale by subtracting the mean and dividing by the standard deviation. Now every variable has mean = 0 and standard deviation = 1, regardless of whether it was originally in percent or dollars.

### Step 2: Find the "Best Summary Direction"

PCA finds the single linear combination of all 6 variables that captures the most variation across counties. Mathematically:

```
ADI_score = w1*(poverty) + w2*(unemployment) + w3*(no_diploma) + w4*(housing_burden) + w5*(-income) + w6*(child_poverty)
```

The weights (w1 through w6) are chosen to maximize the spread of county scores. Counties that are consistently high on all 6 indicators get high ADI scores. Counties that are consistently low get low scores.

### Step 3: Extract the Score

The first principal component (PC1) IS the ADI score. In our data, PC1 explains 58.7% of the total variance across all 6 variables. This means one number captures more than half of all the information contained in 6 different measurements.

### Step 4: Convert to Percentile

The raw PC1 score is converted to a national percentile rank (0 to 100) for easier interpretation. A county at the 80th percentile is more deprived than 80% of all US counties.

## Why 58.7% Variance Explained is Good

When you combine 6 variables into 1 score, the maximum possible variance explained is 100% (if all 6 variables were perfectly correlated). The minimum useful threshold is about 40%. Our 58.7% indicates:

- The 6 indicators share a strong common factor (socioeconomic deprivation)
- But they also have unique variation (each tells you something different)
- One score is a good summary without losing too much information

## Why We Constructed Our Own ADI (Rather Than Using the Pre-Built Neighborhood Atlas)

The University of Wisconsin Neighborhood Atlas provides a validated, downloadable ADI - but only at the Census block group and ZIP code level. **No pre-built county-level ADI exists.**

### Why not just download the Neighborhood Atlas ADI?

| Issue | Explanation |
|-------|-------------|
| **Resolution mismatch** | Neighborhood Atlas ADI is at block group (~600-3,000 people) or ZIP code level. Our unit of analysis is the county (~100,000 people). |
| **No county product exists** | There is simply no downloadable county-level ADI from any standard source. |
| **Aggregation problems** | Averaging block group ADIs up to counties introduces ecological fallacy (a county with one rich area and one poor area averages to "middle"), requires arbitrary weighting decisions, and is biased by suppressed/missing block groups. |
| **Our predictors must match** | SVI is published at the county level. For a valid head-to-head comparison, ADI must also be at the county level. |

### How Mango et al. (JACR 2023) Used ADI Differently

Mango et al. studied breast imaging accreditation at the ZIP code level. The Neighborhood Atlas provides ZIP-level ADI directly, so they could simply download and merge. They also used ADI as a binary classifier (top 3% vs bottom 3%) with chi-square tests.

Our study differs in three key ways:
1. **County-level unit** (no pre-built ADI available) - we must construct our own
2. **Continuous predictor** (per 10-percentile in regression) - more statistical power than binary extremes
3. **Count-based outcome** (negative binomial) - more information than presence/absence

### Our Solution: Replicate the Validated PCA Methodology at County Level

We applied the same PCA approach that Singh (2003) and Kind/Buckingham (2018) used, but computed directly on county-level ACS data. This is standard practice when the geographic unit differs from published ADI products.

## Why This Approach is Validated

This is not a new or experimental method. It has been used in published research for decades:

- **Singh (2003)** used PCA of Census variables to create the original ADI (cited 2,500+ times)
- **Kind and Buckingham (2018)** updated the ADI using PCA in the New England Journal of Medicine
- **Mango et al. (2023)** applied the pre-built ADI to breast imaging accreditation disparities at the ZIP level

We follow the same PCA methodology, applied at the county level to cardiac imaging - extending the Mango et al. framework with more sophisticated statistical methods.

## The Key Result: ADI Finds What SVI Misses

| Predictor | CMR IRR | p-value |
|-----------|---------|---------|
| SVI (CDC composite of 16 variables) | 0.992 | 0.681 (not significant) |
| ADI (PCA of 6 economic variables) | 0.937 | 0.002 (significant) |

The SVI dilutes the economic signal by including non-economic themes (minority status, disability, vehicle access). ADI, by focusing purely on socioeconomic indicators via PCA, isolates the economic component and reveals a true association with CMR access.

## Analogy

Think of it like a medical test:

- **SVI** is like a broad screening panel that tests for many things at once. It may miss subtle findings because of noise from unrelated tests.
- **ADI (via PCA)** is like a targeted test focused specifically on the condition you are looking for (economic deprivation). It has better sensitivity for that specific question.

Both have their place, but for the question "does economic deprivation predict imaging access?" the focused measure (ADI) outperforms the broad measure (SVI).
