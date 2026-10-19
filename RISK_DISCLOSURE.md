# Risk Disclosure

Signal Nexus Community Edition

English is the canonical text. The Japanese edition is [RISK_DISCLOSURE_JA.md](RISK_DISCLOSURE_JA.md). Read this document before you run the software against a live venue. It describes risks of cryptocurrency and perpetual-DEX activity. It is not a complete list of every risk, and it is not investment advice. The terms of use are in [LICENSE.md](LICENSE.md). The allocation of responsibility is in [DISCLAIMER.md](DISCLAIMER.md).

Signal Nexus can turn a TradingView alert into an order plan and, when you set a live execution mode, can send that order to a venue. The analytics views show records the system stored. None of that removes the risks below.

## Market Risk

Cryptocurrency prices can move sharply, in either direction, at any hour, including while you are not watching.

A price can gap. A market can become one-sided. An asset can lose most or all of its value. A quoted price on one venue can differ from the price on another.

A workflow that worked in a quiet market can lose money in a volatile one. Automation can send the next order into that move before you intervene.

## Leverage Risk

Futures and perpetual contracts use leverage. Leverage magnifies both gains and losses.

A small price move can wipe out margin. A position can be liquidated. Liquidation can be partial or total, and it can happen at a price worse than the one you last saw.

Funding payments on perpetual contracts can add cost while a position is open. Funding can change sign and size. Those payments are separate from the price move.

Losses on a leveraged position can exceed the amount you first posted, depending on the venue's rules. You can lose more than the `size_quote` figure on a strategy row.

Leaving execution mode unset keeps the order from being sent. Setting a live mode on a leveraged venue accepts this risk.

## Liquidity Risk

A venue can fill an order at a worse price than the price you saw when the alert fired. That difference is slippage. Slippage grows when the book is thin, when the size is large relative to the book, or when the market is moving.

Liquidity can disappear. A pool can be imbalanced. An order book can gap. You may be unable to exit at any acceptable price, or at any price.

A backtest or a stored record does not include the fill you will actually receive on a later day.

## Counterparty Risk

On a centralized exchange, you do not hold the asset in the software. You hold a claim on the exchange. The exchange can halt withdrawals, halt trading, change the contract, restrict your account, or become insolvent.

The exchange can be hacked, can mismanage client assets, or can refuse a withdrawal. The Author does not custody your funds and cannot reverse an exchange's decision.

An integration such as MEXC is a technical path. It is not insurance and it is not a credit judgment.

## Smart Contract Risk

On a DEX, a trade is executed by smart contracts and by the wallets and permissions those contracts use. A contract can contain a bug. An upgrade can change behavior. An admin key, a guardian, or a governance action can alter a market.

Bridges, routers, and approval grants can be abused. A signature you did not intend, or an approval you left in place, can move assets.

A hack or a bug can drain a pool. Transactions on a public chain are generally irreversible. The Author cannot roll back a chain, a pool, or a wallet.

An integration such as Arcus is a technical path. It is not an audit of the protocol.

## Infrastructure Risk

The path from an alert to a venue crosses systems that can fail independently.

An exchange API can change, rate-limit, or return an error. An RPC endpoint can stall, reorder, or drop a request. An oracle can report a stale, wrong, or manipulated price. A webhook can arrive late, arrive twice, or not arrive.

The software can lose data, store a partial record, or fail in the middle of a plan. A notification copy, including a Discord message, can be missing while the database row exists, or the reverse.

A clock skew, a process restart, or a full disk can change what gets sent and what gets stored. A health check that returns success does not mean a later order will succeed.

You are responsible for the host, the database, the secrets, and the network you chose.

## Operational Risk

Most live losses of this kind start from configuration and operation.

A wrong symbol, a wrong venue, a wrong side, or a wrong `size_quote` will be executed as written when the mode is live. A strategy row that does not match the alert is rejected. A strategy row that matches, and that you did not mean to arm, is not rejected.

A leaked webhook secret allows the holder to submit alerts. A leaked venue key allows the holder to act as you at the venue. A weak or reused portal password exposes the operational views on a host you published.

Leaving the kill switch off, pointing at the wrong environment, or treating a dry-run record as if it were a live fill are operator errors. The software does not know your intent beyond the configuration you supplied.

Test with execution mode unset. Read the audit record before you send a live order.

## Regulatory Risk

Cryptocurrency, derivatives, and automated trading are regulated differently across countries, and the rules change.

An activity that is lawful for you today can become restricted. A venue that serves your region today can withdraw. Perpetual contracts, leverage, and solicitation of other people raise additional rules.

You are responsible for knowing whether your use is lawful where you are, and where the venue operates. The Author does not represent that the Community Edition, or your use of it, complies with any law.

This document is not legal advice. A personal, educational, or research use can still be regulated as trading.

## Performance Disclaimer

The statement that past results do not guarantee a future result is in [DISCLAIMER.md](DISCLAIMER.md). This section describes how a stored result can differ from a later fill.

A strategy that was profitable in a stored sample can lose money later. A fill in the record is not the fill you will get. Survivorship, fees, funding, slippage, and rejected orders can reverse a result that looks positive on a screen.

No performance figure published with Signal Nexus is a promise, a track record offered for sale, or a solicitation.
