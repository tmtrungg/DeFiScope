# Supplementary Material

## A. Full Version of Fine-tuning Prompt Template

Following figure shows the full version of prompt template used in fine-tuning, mentioned in §IV, in the main part of the paper.

Above the dashed line is the first instruction, which requires the LLM to extract the price calculation model from the provided code. `{code}` is the placeholder for the code snippet of price calculation functions. Below the dashed line, we guide the LLM to evaluate the credibility of four statements based on the price model extracted from step 1 and the tokens’ balance change. 

![fine-tuning_prompt_template](https://github.com/user-attachments/assets/0cef326d-67f9-4b01-894b-954d3d9f04d3)

## B. Example Prompt and Response of the Motivating Example

The figure below demonstrates a simplified version of the Type-I prompt used and the response produced by our fine-tuned LLM for inferring price changes of the motivating example in §II-C, in the main part of the paper.

From the motivating example’s response shown in the right-hand section, the LLM initially extracts the code of price calculation-related functions, followed by an high-level summary. In this example, it accurately identifies the underlying price model (see eq. (1) in the main part of the paper) — the price of *sUSDe* is determined by the median of multiple prices.

![UwULend_prompt_response](https://github.com/user-attachments/assets/985057f8-0a8d-4582-96b3-8953a56e4964)

## C. Detailed Type-II Prompt Template

The following figure illustrates the Type-II prompt template mentioned in §IV, in the main part of the paper.

It is used in *Customized Inference Process*, for inferring the trend of price changes in closed source two-token liquidity pools. The primary distinction between the Type-I prompt and the Type-II prompt lies in replacing the first instruction with a description of the liquidity pool, informing the LLM that the pool’s price model aligns with CPMM.

![Type-II_prompt](https://github.com/user-attachments/assets/5d8bb668-a1c4-4aa9-b8c9-8a75baf89da1)

## D. A Case Study of Type-II Prompt

The figure below shows a use case of the Type-II prompt. 

The contract (0x2120...3379) is a closed source DEX contract that allows users to trade SVT and USDT. While recovering the DeFi operations, this contract was identified as a two-token liquidity pool. So, we applied the Type-II prompt to inferring the token price trend in its transactions. 

As shown by the LLM response in figure, the primary difference from the response to a Type-I prompt lies in the absence of the analysis on the price model; instead, the scoring is directly yielded. The is because the prompt itself assumes that the CPMM is employed in this contract. Regarding the CPMM, the relationship between token price and token balance is quite standardized, i.e., the direction of balance change is opposite to that of price change.

![prompt_response_of_t2_prompt_case_study](https://github.com/user-attachments/assets/a0f11d5e-f5ad-4567-beb8-2d442aa0df3c)

## E. Full List of Top-10 High-value DeFi Application Across 3 Categories

The design of DeFi operations and the category of transfer actions in §V, in the main part of the paper, is based on an in-depth study of the high-value DeFi applications listed in the table below as of August 2024.

|   DEX App   |   TVL    |  Lending App  |   TVL    | Yield farming App  |   TVL    |
| :---------: | :------: | :-----------: | :------: | :----------------: | :------: |
|   Uniswap   |  \$4.8B  |   Compound    |  \$2.0B  |       Pendle       |  \$2.8B  |
|    Curve    |  \$1.9B  |     AAVE      | \$12.3B  |   Convex Finance   |  \$1.1B  |
|  Balancer   | \$777.2M |    Morpho     |  \$1.5B  |        Aura        | \$361.9M |
|    Sushi    | \$250.2M |   Fraxlend    | \$134.4M |       Magpie       | \$192.5M |
| PancakeSwap |  \$1.7B  |     Venus     |  \$1.5B  |      StakeDAO      | \$78.8M  |
|    1inch    | \$4.58M  |    Strike     |  \$9.7M  | Equilibria Finance | \$80.0M  |
|  ParaSwap   | \$6.34M  |    Planet     |  \$1.2M  |    Kine Finance    |  \$8.0M  |
|  ShibaSwap  | \$18.19M | Kinza Finance | \$42.8M  |  Dot Dot Finance   |  \$2.1M  |
|   BiSwap    | \$27.1M  |    Radiant    |  \$7.8M  |      Solo Top      |  \$1.8M  |
|    MDEX     | \$16.0M  |     Ambit     |   \$6M   |  Jetfuel Finance   |  \$1.5M  |

## F. Detailed Discussion of Attack Types and Patterns

In this section, we will illustrate the attack types and patterns mentioned in §VI, in the main part of the paper.

**Buy** **\&** **Sell.** In this type of attack strategy, the attacker primarily profits by first buying $Token_y$ with $Token_x$ through a swap in $Pool_{buy}$ and then selling $Token_y$ for $Token_z$ through a swap in $Pool_{sell}$. $Token_x$ and $Token_z$ can be the same or different tokens. In the attack against ElephantMoney, the attacker first conducted a swap in $Pool_{buy}$ to exchange WBNB for ELEPHANT and then invoked the `mint` function, which triggered a swap in $Pool_{sell}$ to exchange ELEPHANT for WBNB, resulting in a price increase of ELEPHANT in $Pool_{sell}$. Ultimately, the attacker utilized a reverse swap in $Pool_{sell}$ to obtain WBNB by selling ELEPHANT at the manipulated price. We design Pattern I based on this attack and subsequently generalize it to Pattern II. The major difference between these two patterns is that the token price is manipulated before the first swap in Pattern II, allowing the price of tokens in either $Pool_{buy}$ or $Pool_{sell}$ to be manipulated.

**Deposit** **\&** **Borrow.** In this type, the attacker inflates the price of the deposited tokens or deflates the price of the borrowed assets as calculated by $Contract_{borrow}$, bypassing the protective mechanism of over-collateralization, thereby borrowing more assets than the actual value of the collateral. In the Cream Finance incident, the attacker first deposited yUSD as collateral and obtained an equivalent amount of crYUSD as proof of deposit, then inflated the price of yUSD calculated by $Contract_{borrow}$ by transferring a large quantity of yCrv to a specific contract account. Finally, using yUSD as collateral, the attacker borrowed a large amount of assets, which far exceeded the actual value of the deposited yUSD, from $Contract_{borrow}$. We design Pattern III based on this attack and then generalize it to Pattern IV. Pattern IV differs from Pattern III in that the attacker can preemptively increase the price of tokens designated for deposit or decrease the price of assets intended for borrowing as calculated by $Contract_{borrow}$ before the deposit operation. In particular, the motivating example in §II, in the main part of the paper, conforms to Pattern IV.

**Stake** **\&** **Claim.** This attack type primarily targets yield-farming protocols that offer staking services. Typically, an attacker first stakes $Token_x$ into the application in one transaction. The share ratio of the user is calculated based on the value and quantity of the staked asset in real-time and is stored in the state variables. Then, the attacker decreases the calculated price of $Token_y$ in $Contract_{claim}$ and subsequently claims $Token_y$ from the contract. $Token_x$ and $Token_y$ can be the same or different tokens. We derive Pattern V based on the analysis of the attack against ATK. Specifically, in the first transaction, the attacker initially staked ATK into $Contract_{stake}$. Since the staking service required that the ATK be held for 24 hours by the contract account before claiming, the attacker waited for a period and executed the second transaction, exploiting a flash loan to deflate the price of ATK in $Contract_{claim}$, subsequently claiming back an amount of ATK significantly higher than the appropriate quantity. Considering that the attacker can inflate the price of tokens intended for staking beforehand to get an incorrectly calculated share ratio, we further derive Pattern VI from Pattern V.

**Deposit** **\&** **Withdraw.** In this attack type, the attacker exploits vulnerabilities in the token pricing mechanism within the deposit or withdrawal contract to conduct price manipulation attacks. We design and generalize Pattern VII based on the Harvest attack. In this hack, the attacker first deposited USDC ($Token_x$) in $Contract_{deposit}$ and received fUSDC ($Token_y$) as proof. Then, by exchanging USDC for USDT, the price of USDC calculated by $Contract_{withdrawal}$ decreased, and the attacker withdrew an excessive amount of USDC ($Token_z$) from $Contract_{withdrawal}$ by burning fUSDC. In this case, $Token_x$ and $Token_z$ are the same; however, some protocols, such as [LUSD](https://bscscan.com/address/0xdec12a1dcbc1f741ccd02dfd862ab226f6383003), allow different tokens for deposit and withdrawal. Besides deflating the price of tokens to be withdrawn, the attacker can also inflate the price of tokens used for calculating the withdrawal amount, i.e., $Token_y$. If the attacker manipulates the token price before depositing, the price of tokens involved in the deposit can also be affected. Based on this reason, we generalize Pattern VII to create Pattern VIII.

## G. Details of False Positives

The following table presents the details of six false positives discovered in *D2* (suspicious transactions) dataset during our experiments described in §VII-C, in the main part of the paper. The reason for these false positives is that their transactions involve two contract accounts that were created three months ago by the transaction initiator. Any fund transfers among these accounts and the initiator should be considered benign operations rather than price manipulation operations. Yet, these accounts were incorrectly marked as closed-source DEXes in the detection, leading to false inferences. Such false positives could be mitigated by conducting a historical analysis of account ownership relationships and clustering user accounts that are controlled by the same owners.

| Transaction hash | Chain |  Block   |   Type    | Root Cause  |
| :--------------: | :---: | :------: | :-------: | :---------: |
|    0x130c6370    |  BSC  | 38218540 |  Benign   |      -      |
|    0x4b59af93    |  BSC  | 38218538 |  Benign   |      -      |
|    0xe158a2b9    |  BSC  | 38218537 |  Benign   |      -      |
|    0x59942848    |  BSC  | 38218536 |  Benign   |      -      |
|    0x2e9ceb16    |  BSC  | 38218539 |  Benign   |      -      |
|    0x640ce34c    |  BSC  | 11403670 | Malicious | Logic issue |

## H. Details of detected attacks on other EVM-compatible chains

Ethereum and BSC together hold 64.1% of the total value locked (TVL) across all blockchain networks, making them the most representative platforms for DeFi applications. Moreover, from August 2021 to August 2025, 84% of recorded price manipulation attacks sourced from mainstream platforms ([DeFiHackLabs](https://github.com/SunWeb3Sec/DeFiHackLabs) and [SlowMist](https://www.slowmist.com/)) occurred on Ethereum and BSC. Therefore, focusing our evaluation on these two chains captures the majority of real-world attacks.

Nevertheless, DeFiScope is generalizable to other EVM-compatible chains, such as Polygon and Arbitrum. The following table summarizes the price manipulation attacks detected by DeFiScope on these chains.

| Project name  |                   Attack transaction hash                    | Blockchain platform |
| :-----------: | :----------------------------------------------------------: | :-----------------: |
|    BonqDAO    | 0x31957ecc43774d19f54d9968e95c69c882468b46860f921668f2c55fadd51b19 |       Polygon       |
|     MonoX     | 0x5a03b9c03eedcb9ec6e70c6841eaa4976a732d050a6218969e39483bb3004d5d |       Polygon       |
|     Gamma     | 0xa96584f8ab7c27daea33798bb8a66286c75a2ba57eee3b4192c771f4eb4ac609 |      Arbitrum       |
|  LavaLending  | 0xb5cfa4ae4d6e459ba285fec7f31caf8885e2285a0b4ff62f66b43e280c947216 |      Arbitrum       |
|   BelugaDex   | 0x57c96e320a3b885fabd95dd476d43c0d0fb10500d940d9594d4a458471a87abe |      Arbitrum       |
| NeutraFinance | 0x6301d4c9f7ac1c96a65e83be6ea2fff5000f0b1939ad24955e40890bd9fe6122 |      Arbitrum       |
|    Themis     | 0xff368294ccb3cd6e7e263526b5c820b22dea2b2fd8617119ba5c3ab8417403d8 |      Arbitrum       |

## I. Details of McNemar test results on RQ1

To evaluate the significance of DeFiScope's performance improvements over baselines, we conducted the McNemar test on the evaluation result of RQ1: Detection Effectiveness. This test is well-suited for binary classification results and allows us to assess whether the observed differences in detection performance between DeFiScope and other tools are statistically significant. The following table presents the McNemar test results between DeFiScope and each baseline. The upper section shows the contingency tables for each pairwise comparison, indicating the number of attacks detected and missed by both DeFiScope and the respective baseline. The lower section reports the $\chi^2$ statistic and the corresponding p-value. All p-values are well below the common significance threshold of 0.05, demonstrating that the performance improvements of DeFiScope over each baseline are statistically significant.

|               |              |         DeFiRanger          |         DeFiTainter         |           DeFort            |
| :-----------: | :----------: | :-------------------------: | :-------------------------: | :-------------------------: |
|               |              | Detected       Not Detected | Detected       Not Detected | Detected       Not Detected |
| **DeFiScope** |   Detected   |  43                     33  |  28                     48  |  39                     37  |
| **DeFiScope** | Not Detected |  6                      13  | 6                        13 |  11                      8  |
|               |    Result    |        $\chi^2$=17.3        |        $\chi^2$=31.1        |        $\chi^2$=13.0        |
|               |    Result    |    p=$3.1\times10^{-5}$     |    p=$2.4\times10^{-8}$     |    p=$3.1\times10^{-4}$     |

## J. Fine-tuned Phi-3 model on HuggingFace

We have released the fine-tuned Phi-3 model demonstrated in §VIII (Discussion) on HuggingFace:
https://huggingface.co/RocketRaccoonnn/Phi-3-medium-128k-instruct_LoRA_CASUAL_LM_lora_v2

## K. Quantitative Comparison between Transfer Graph and Cash Flow Tree (CFT)

Although DeFiRanger has evaluated the effectiveness of CFT in their original paper, neither their implementation nor the dataset was open-sourced. Following DeFiRanger's data collection methodology, we gathered 1,000 consecutive transactions on Ethereum, starting from block height 23,289,244. Collecting transactions continuously helps mitigate sampling biases and provides a representative set of real-world DeFi operations. We manually checked each transaction and identified 204 DeFi operations in total, with the distribution of each type shown as following table:

|       | Swap | Deposit | Withdraw | Stake | Claim | Sum. |
| :---: | :--: | :-----: | :------: | :---: | :---: | :--: |
| #Case | 158  |    6    |    8     |  12   |  20   | 204  |

To evaluate CFT, we reproduced its implementation based on the description in DeFiRanger's paper. We clarify that, as stated in §VII-A (RQ1: Detection Effectiveness), while evaluating the performance of DeFiRanger, for the attack cases sourced from DeFiRanger's paper, we directly used its results. For all other cases, we applied our reproduced implementation.

We followed the same evaluation metrics as DeFiRanger, i.e., precision ($\frac{\\#TP}{\\#TP+\\#FP}$) and true positive rate---TPR ($\frac{\\#TP}{\\#TP+\\#FN}$). On the 1000 transactions, TG identified 189 DeFi operations, of which 186 were correct (TP) and 3 were incorrect (FP), while missing 18 operations (FN). This yields a precision of 0.984 and a TPR of 0.912. In comparison, CFT missed 90 (FN) operations and produced 1 incorrect operation (FP), achieving a slightly higher precision of 0.991, but a significantly lower TPR of 0.559.

These results demonstrate that TG is more effective at recovering DeFi operations, achieving a substantially higher TPR while maintaining a precision comparable to CFT.

![uncommon_common](https://github.com/user-attachments/assets/5c6e4c0e-75d1-4740-a539-fac805ec3b3c)

After taking an in-depth look at the false negatives and false positives of TG, we divided the 18 FNs into 3 categories:

- A few uncommon designs and execution of DeFi operations led to 12 false negatives (FNs) and 3 false positives (FPs). For instance, some swap operations had an atypical transfer order (as shown in above figure). Since TG requires the time indices of transfers within a swap to be monotonically increasing (as illustrated in §V-B), this uncommon order of transfers violated our rule for identifying swaps, resulting in FNs. The FPs occurred in cases that resembled withdrawals (i.e., transferring a token to the zero address and receiving another token from the protocol) or deposits (i.e., transferring a token to the protocol and receiving another token via minting), but were in fact swap operations. This mismatch caused TG to misclassify the operation type.
- A few claim operations (4 FNs) were missed because our tool could not correctly identify the beneficiary. In these cases, there was no direct relationship between the relevant accounts in the transaction, preventing our tool from recognizing that the beneficiary was controlled by the user.
- Two DeFi operations in the transactions involved only transfers among contracts within the protocol, without any user-involved transfers. Since our tool is designed to recover user-involved DeFi operations, it did not identify these cases.

Next, we analyzed the false negatives of CFT. We found that 75 out of its 90 false negatives were complex swap operations involving multiple relayers, accounting for all multi-relayer swaps among the 158 identified swap operations. In such swaps, several accounts may relay tokens --- either as liquidity pools swapping between different tokens or as simple pass-through addresses transferring the same token. This complexity made it challenging for CFT to accurately trace the token flows, resulting in missed detections. In contrast, TG only missed 8 of these operations due to uncommon transfer orders, as explained above, yielding an 89.3% improvement over CFT on recovering this type of swap operations.

![case_study_tg_cft](https://github.com/user-attachments/assets/38e1e6c6-ce07-4483-9a09-5678d09459bd)

To further illustrate the difference between TG and CFT, we analyze a [transaction](https://app.blocksec.com/explorer/tx/eth/0x5f6377f1cefd58d707f6d5ab6b13aae8b01116dfd9ea4c10a53c3769426beade) as case study. Above figure presents the simplified results recovered by both methods. In this swap operation, there are one user account $U$ and three relayers, i.e., $A$, $B$ and $C$, where $A$ and $C$ only forward the tokens they receive (either token X or token Y), while $B$ acts as a liquidity pool swapping between token X and token Y. By design, CFT connects $Tr1$ and $Tr2$, $Tr3$ and $Tr4$ respectively according to its rules, but it could not connect $Tr2$ and $Tr3$ because $A$ and $C$ are not user accounts, violating CFT's combination rules. As a result, CFT failed to identify the swap operation. In comparison, TG builds a directed graph over all transfers and identifies cycles as swap operations. Here, TG successfully identifies the cycle $U \rightarrow A \rightarrow B \rightarrow C \rightarrow U$, which starts and ends with the user and satisfies rules (i) each edge is transferring token,i.e., no burning or minting; (ii) time indices of edges are monotonically increasing; and (iii) the token sent by the user initially differs from the token received at the end. Hence, TG successfully recovers the swap operation.

As discussed above, 75 out of the 158 identified swap operations are multi-relayer swaps, highlighting their high prevalence in real-world scenarios. Notably, this type of swap also appears in price manipulation attacks, such as those targeting [AutoSharkFinance\_2](https://app.blocksec.com/explorer/tx/bsc/0xfbe65ad3eed6b28d59bf6043debf1166d3420d214020ef54f12d2e0583a66f13) and [STM](https://app.blocksec.com/explorer/tx/bsc/0x849ed7f687cc2ebd1f7c4bed0849893e829a74f512b7f4a18aea39a3ef4d83b1) in the *D1* dataset used in our evaluation. Since CFT fails to recover these operations, DeFiRanger is unable to detect the corresponding attacks. In contrast, DeFiScope, powered by TG, successfully recoveries the DeFi operations and identifies the attack. This demonstrates that TG is more effective than CFT, particularly in handling complex operations like multi-relayer swaps.

## L. Detailed Time Cost Breakdown of Each Main Stage

The below table presents the detailed time cost breakdown for each main stage of DeFiScope's workflow. More than half of runtime is spent on price change inference, which takes an average of 1.40 seconds per transaction, followed by static analysis at 0.97 seconds. Data retrieve and pre-process incurs a small overhead of 0.17 seconds, whereas the time cost on DeFi operation recovery and attack detection is negligible.

| Stage                         | Corresponding steps in the workflow | Ave. time cost (s) |
| ----------------------------- | ----------------------------------- | ------------------ |
| Data Retrieve and Pre-Process | Step 1                              | 0.17               |
| Static Analysis               | Step 2, 5                           | 0.97               |
| DeFi Operation Recovery       | Step 3, 4                           | < 0.01             |
| Price Change Inference        | Step 6, 7, 8                        | 1.40               |
| Attack Detection              | Step 9                              | < 0.01             |
| Total                         | All steps                           | 2.54               |

