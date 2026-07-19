"""Topic engine for enterprise-finance lead-generation content."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import logging
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TopicIdea:
    topic_type: str
    target_customer: str
    pain_point: str
    article_angle: str
    suggested_title: str
    conversion_goal: str


class TopicEngine:
    """Generate practical WeChat topics for small-business financing leads."""

    TOPIC_TYPES = (
        "老板痛点类",
        "银行拒贷类",
        "企业征信类",
        "额度提升类",
        "续贷风险类",
        "经营贷申请类",
        "现金流周转类",
        "真实案例拆解类",
    )

    _TOPICS = (
        TopicIdea(
            "老板痛点类",
            "近期订单增加、账期拉长的小微企业老板",
            "账上利润看着不差，但现金流总是卡在应收账款和库存里",
            "从老板真实经营场景切入，解释银行为什么更看重流水稳定性和还款来源",
            "老板账上有利润，为什么银行还是不批贷款？",
            "引导企业主做一次融资体检，判断现金流短板和可申请额度",
        ),
        TopicIdea(
            "银行拒贷类",
            "刚被银行拒贷、想知道原因的企业主",
            "材料交了很多，银行只说综合评分不足，老板不知道该从哪里补救",
            "拆解被拒背后的征信、流水、负债、纳税和行业风险信号",
            "银行拒贷后，老板先别急着换银行",
            "引导提交基础资料，做拒贷原因复盘和二次申请路径判断",
        ),
        TopicIdea(
            "企业征信类",
            "企业征信有查询、逾期或担保记录的老板",
            "不知道企业征信上的小问题会不会影响授信审批",
            "用案例说明企业征信、法人征信和关联企业风险如何影响审批",
            "企业征信有这3个信号，银行审批会变谨慎",
            "引导预约融资诊断，提前排查征信和关联风险",
        ),
        TopicIdea(
            "额度提升类",
            "已有授信但额度不够用的企业老板",
            "银行给的额度低，无法覆盖采购、发薪或项目周转需求",
            "解释额度低不是单纯产品问题，而是经营数据和资产负债结构问题",
            "经营贷额度低，通常不是银行故意卡你",
            "引导做额度提升评估，梳理流水、纳税、资产和负债优化空间",
        ),
        TopicIdea(
            "续贷风险类",
            "贷款即将到期、担心续不上贷的企业主",
            "临近到期才发现流水下降、查询增多或负债升高，续贷不稳",
            "提醒老板提前90天体检授信条件，避免到期被动周转",
            "贷款快到期才准备续贷，老板最容易踩这4个坑",
            "引导预约续贷风险排查，制定到期前资金安排",
        ),
        TopicIdea(
            "经营贷申请类",
            "第一次申请经营贷的个体户和小微企业主",
            "听说经营贷额度高，但不知道银行到底看什么",
            "把经营贷审批拆成主体、流水、用途、还款来源和征信五项",
            "经营贷不是有营业执照就能批",
            "引导做经营贷申请资格初筛，降低盲目申请造成的查询损耗",
        ),
        TopicIdea(
            "现金流周转类",
            "被账期、库存、工资和房租压住现金流的老板",
            "业务还在做，但资金链一紧就影响采购、交付和员工工资",
            "从现金流缺口倒推融资时点和融资方式，而不是临时到处借钱",
            "现金流一紧，老板不要只盯着利率",
            "引导填写现金流缺口，匹配短期周转或中长期授信思路",
        ),
        TopicIdea(
            "真实案例拆解类",
            "想参考同类企业融资路径的老板",
            "看了很多贷款知识，仍不知道自己的企业适合什么方案",
            "用匿名案例拆解被拒、调整资料、重做融资顺序后的变化",
            "一家贸易公司被拒贷后，额度怎么重新做起来？",
            "引导企业主提交企业情况，获取同类型融资路径参考",
        ),
    )

    _INDUSTRY_LAW_TOPICS = (
        {"core_law":"银行不是把钱借给最缺钱的人，而是把钱借给最有能力还钱的人。","source_title":"银行为什么不把钱借给最缺钱的人","suggested_title":"贷款行业有个真相：越缺钱，反而越难贷到钱","target_customer":"资金紧张、回款放缓的小微企业主","common_misunderstanding":"公司越缺钱，银行越应该支持。","bank_logic":"银行先看第一还款来源、现金流稳定性和偿债能力。","article_angle":"解释资金缺口与还款来源的错位。"},
        {"core_law":"企业想借多少不决定额度，企业能承受多少负债才决定额度。","source_title":"企业想贷500万，银行为什么只批100万","suggested_title":"企业想贷500万，银行为什么只批100万？","target_customer":"营收不错但额度不足的企业主","common_misunderstanding":"营收高就该拿到与缺口相等的额度。","bank_logic":"银行会结合现金流、利润和现有负债做压力测试。","article_angle":"拆解额度与偿债上限的关系。"},
        {"core_law":"银行看可验证事实，不看口头故事。","source_title":"银行审批为什么不相信老板讲的故事","suggested_title":"老板说生意很好，银行为什么还要看证据？","target_customer":"有订单但材料印证不足的企业主","common_misunderstanding":"有订单就一定会获批。","bank_logic":"流水、合同、发票、纳税和征信必须互相印证。","article_angle":"把经营故事变成银行能验证的证据链。"},
        {"core_law":"企业条件决定融资上限，产品匹配决定审批结果。","source_title":"为什么产品选错比企业资质差更容易被拒","suggested_title":"产品选错，比企业资质差更容易被拒","target_customer":"申请不顺的企业主","common_misunderstanding":"条件好就应该找利率最低的产品。","bank_logic":"不同产品的准入条件、用途和申请顺序不同。","article_angle":"解释产品匹配如何影响结果。"},
        {"core_law":"客户买的不是贷款，而是融资结果的确定性。","source_title":"为什么融资顾问不能只给客户报利率","suggested_title":"融资服务真正卖的，不是一张利率报价单","target_customer":"比较融资服务的企业主","common_misunderstanding":"谁报的利率低，谁更有价值。","bank_logic":"利率只是风险定价结果。","article_angle":"说明融资服务如何降低试错。"},
        {"core_law":"融资最好的时间不是最缺钱的时候，而是经营和信用状态最好的时候。","source_title":"为什么资金越紧张，越不应该盲目申请贷款","suggested_title":"资金越紧张，为什么越不能盲目申请贷款？","target_customer":"贷款将到期的企业主","common_misunderstanding":"越缺钱越要同时申请多家银行。","bank_logic":"查询增加和流水下滑会抬升风险。","article_angle":"解释融资时点决定选择空间。"},
        {"core_law":"企业越着急，融资风险越高。","source_title":"借新还旧，什么时候是周转，什么时候是风险","suggested_title":"越着急借钱，为什么越容易把融资做坏？","target_customer":"频繁申请的企业主","common_misunderstanding":"先借到钱再说。","bank_logic":"负债滚动和还款来源不清会积累风险。","article_angle":"区分正常周转和以贷养贷。"},
        {"core_law":"长期价值来自经营能力、信用积累和持续融资规划。","source_title":"企业融资为什么不是一次性交易","suggested_title":"一笔贷款做完后，企业为什么还要做融资规划？","target_customer":"准备续贷或提额的企业主","common_misunderstanding":"贷款到账后融资工作就结束。","bank_logic":"银行持续观察经营、还款和信用变化。","article_angle":"说明融资规划。"},
    )
    @classmethod
    def generate_industry_law_topics(cls, limit: int = 8) -> list[dict[str, Any]]:
        safe_limit=max(1,min(int(limit or 8),len(cls._INDUSTRY_LAW_TOPICS)))
        return [{"article_type":"industry_law","topic_type":"贷款底层规律","category":"贷款行业底层规律","conversion_goal":"企业融资体检",**item} for item in cls._INDUSTRY_LAW_TOPICS[:safe_limit]]
    @classmethod
    def generate_topics(cls, limit: int = 8, business_context: str | None = None) -> list[dict[str, Any]]:
        """Return topic ideas with every required conversion field populated."""
        try:
            safe_limit = max(1, min(int(limit or 8), len(cls._TOPICS)))
            topics = list(cls._TOPICS[:safe_limit])
            safe_context = str(business_context or "").strip()
            if safe_context:
                topics = [
                    TopicIdea(
                        item.topic_type,
                        item.target_customer,
                        item.pain_point,
                        f"{item.article_angle}；结合「{safe_context}」场景做本地化表达",
                        item.suggested_title,
                        item.conversion_goal,
                    )
                    for item in topics
                ]
            return [asdict(item) for item in topics]
        except Exception as exc:
            logger.exception("[content-growth-dashboard-error] topic generation error=%s", exc)
            return [asdict(item) for item in cls._TOPICS[:8]]

    @classmethod
    def recommend_next_topic(cls, weak_area: str = "") -> dict[str, Any]:
        """Pick a next topic based on the weakest growth signal."""
        try:
            weak = str(weak_area or "").strip()
            if "标题" in weak or "点击" in weak:
                return asdict(cls._TOPICS[1])
            if "CTA" in weak or "咨询" in weak or "扫码" in weak:
                return asdict(cls._TOPICS[7])
            if "内容" in weak or "收藏" in weak:
                return asdict(cls._TOPICS[3])
            return asdict(cls._TOPICS[0])
        except Exception:
            return asdict(cls._TOPICS[0])
