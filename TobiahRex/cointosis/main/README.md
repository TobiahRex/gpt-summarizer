# Cointosis

An algorithmic trading framework by Tobiah Rex

_Etymology:_
> "Your weapon is made using cortosis. It's strong enough to stand up against anything, even a lightsaber."
―Trask Ulgo, *Star Wars Knights of the Old Republic*
### Cloud Architecture
<img src="https://imgur.com/tf2tBnm.png" />

## Trading Model
The app is setup to allow for multiple version trading models to be run simultaneously. The model's are deployed via AWS Lambda functions. The Lambda's are ran on cron jobs, at a N-minute interval. Each interval of time performs a pipeline set of operations in a unidirectional manner.
1. Market *Analysis*
2. *Trading* per Analysis' recommended actions.
3. *Calculation* of Position Changes
4. *Notification* of Status
5. *Data Saving* of actions taken

These 5 steps are fundamental to any trading model dynamics and they constitute a "Trading Pipeline".

### 1. Analysis

#### 1.1 - WHAT
**Big Picture:**
This is the heart of the trading pipeline; the _Brain_ of the algorithmic trading robot. Everything outside of Analysis would be considered the _Body_.  Ideally, the code for the subsequent 4 steps need never change to improve the models performance capabilities.  As of May 2022, the Trading model is configured for Forex Trading only, however the code has been configured in such a way for the eventual expansion into Equities and Cryptos.

**Isolation for Flexibility:**
The analysis module is designed to be ran in isolation from any other modules, and represents a pure-functional-paradigm where there only ever exists a single point of entry and a single point of output. There are side-effects (API calls to 3rd party entities) however, there is no communication between the Analysis module and the subsequent modules.  Some behavior of the Analysis module can be dynamically influence from environmental variables defined in the global context via AWS's SSM parameter stores however these "levers" are meant to simply allow minor modification of the Analysis output even while the Pipeline is deployed and in an active state without requiring a full re-deployment of small desired changes.

#### 1.2 - HOW
Depending on the active version (*V2* is active as of May 2022), an analysis will analyze the market based on an input of technical analysis data, as well as price action, and the active positions dynamics (e.g. P/L, Drawdown, etc). A *position* is a set of *trades* and an active position means that risk is currently in-play on a market.

 Each *position* has it's own life-cycle and metrics that are evaluated and updated in the *3. Calculation* phase. Each *trade* also, has it's own individual life-cycle and metrics also evaluated and updated in the *Calculation* phase.

The **input** to the Analysis step is a set of indicator data that is then closely inspected to output a recommended set of *actions* by which *2. Trading* can be conducted.

#### 1.3 - WHY

The analysis step is a series of computations, that are ran on data, in order to formulate some sort of actionable decision.

### 2. Trading

#### 2.1 - WHAT

**Big Picture:**
This is the second step of the pipeline. The trading step is where the actual trading of assets takes place. This is where the decisions that were made in the analysis step are put into action.

**Technical:**
The trading step is where the actual trading of assets takes place. This is where the decisions that were made in the analysis step are put into action.

#### 2.2 - HOW

The trading is done via the [Bittrex API](https://bittrex.com/Home/Api).

#### 2.3 - WHY

The trading step is where the actual trading of assets takes place. This is where the decisions that were made in the analysis step are put into action.

### 3. Calculation

#### 3.1 - WHAT

**Big Picture:**
This is the third step of the pipeline. The calculation step is where the position changes that were made in the trading step are calculated. This is where the P/L (Profit/Loss) is calculated.

**Technical:**
The calculation step is where the position changes that were made in the trading step are calculated. This is where the P/L (Profit/Loss) is calculated.

#### 3.2 - HOW

The calculations are done via the [Bittrex API](https://bittrex.com/Home/Api).

#### 3.3 - WHY

The calculation step is where the position changes that were made in the trading step are calculated. This is where the P/L (Profit/Loss) is calculated.

### 4. Notification

#### 4.1 - WHAT

**Big Picture:**
This is the fourth step of the pipeline. The notification step is where the status of the trading model is communicated to the user. This is done via email, SMS, or some other form of communication.

**Technical:**
The notification step is where the status of the trading model is communicated to the user. This is done via email, SMS, or some other form of communication.

#### 4.2 - HOW

The notifications are done via the [Bittrex API](https://bittrex.com/Home/Api).

#### 4.3 - WHY

The notification step is where the status of the trading model is communicated to the user. This is done via email, SMS, or some other form of communication.

### 5. Data Saving

#### 5.1 - WHAT

**Big Picture:**
This is the fifth and final step of the pipeline. The data saving step is where the data that was used in the analysis and trading steps is saved. This data is saved in the database.

**Technical:**
The data saving step is where the data that was used in the analysis and trading steps is saved. This data is saved in the database.

#### 5.2 - HOW

The data is saved in the database.

#### 5.3 - WHY

The data saving step is where the data that was used in the analysis and trading steps is saved. This data is saved in the database.