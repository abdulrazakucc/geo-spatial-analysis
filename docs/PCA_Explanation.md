# How the Economic Deprivation Index (EDI) Is Built with Principal Component Analysis

## The simple explanation

To describe how economically deprived a county is, we use six county measures:

1. Persons below 150% of the federal poverty level
2. Civilian labor force unemployed
3. Adults aged 25 or older without a high-school diploma
4. Housing cost-burdened households
5. Median household income (sign reversed, so higher means poorer)
6. Children in poverty

Each says something about deprivation; none says everything. Principal component
analysis (PCA) combines them into one score.

## Why not just average them?

**Different scales.** Poverty is a percentage; income is in dollars. They cannot
be averaged directly. PCA works on standardized values (each measure rescaled to
mean 0 and standard deviation 1), so the original units no longer matter.

**Overlap.** Some measures move together closely. In these data the correlation
between persons below 150% of the poverty level and children in poverty is 0.86.
A simple average would count that shared poverty signal twice.

**Weights.** After standardization every measure has the same variance, so the
weights PCA assigns are set by how strongly the measures are correlated with one
another, not by how much any one varies on its original scale. Measures that share
more of the common pattern receive larger weights.

## What PCA does

1. **Standardize** the six measures (z-scores).
2. **Find the combination that captures the most shared variation:**

   ```text
   EDI_score = w1*(poverty) + w2*(unemployment) + w3*(no_diploma)
             + w4*(housing_burden) + w5*(-income) + w6*(child_poverty)
   ```

   The weights are the first eigenvector of the correlation matrix.
3. **Use the first principal component (PC1) as the index.** In these data PC1
   explains 58.7% of the variance in the six measures across 3,134 counties, and
   all six load positively on it.
4. **Convert to national percentiles** (0 to 100). A county at the 80th percentile
   is more deprived than 80% of counties.

## How many components?

A second component has an eigenvalue just above 1 (1.03) and is dominated by one
measure, housing cost burden. Horn's parallel analysis compares each eigenvalue
with those obtained from data in which every measure is shuffled independently, so
that any correlation is destroyed; the second eigenvalue is no larger than chance,
and parallel analysis retains one component. The index therefore uses PC1 alone.
The scree plot, biplot and all loadings are in Supplementary Figure S3 and Table S5.

## Why a purpose-built county index?

The Area Deprivation Index (ADI) of Singh (2003), distributed for block groups by
the University of Wisconsin Neighborhood Atlas (Kind and Buckingham, 2018), is a
validated measure, but it is not published for counties. Aggregating block groups
to counties would require weighting choices and would not match the county unit of
the SVI. We therefore built a county-level index from economic measures with the
same general PCA approach. It is called the EDI so that it is never confused with
the ADI; it is not the ADI.

Other studies have used the ADI at finer geography. For example, Mango et al.
(J Am Coll Radiol 2023) used ZIP-level ADI and compared the most and least deprived
extremes. Our study uses counties, a continuous index per 10 percentile points, and
count models of facility numbers.

## What the index showed

| Model, cardiac MR | IRR per 10 percentile points | P |
|---|---|---|
| SVI, unadjusted | 1.00 | 0.980 |
| EDI, unadjusted | 0.95 | 0.003 |
| SVI, adjusted for metropolitan status | 1.00 | 0.854 |
| EDI, adjusted for metropolitan status | 0.99 | 0.699 |

The EDI is associated with lower cardiac MR capacity before adjustment but not
after: the unadjusted association reflects the EDI's correlation with
nonmetropolitan location. The study does not test whether either index predicts
access better than the other or better than geographic measures. Current values
are in `output/validation/manuscript_numbers.json`.
