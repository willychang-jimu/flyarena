"""所有大腦共用的介面。回測、比賽、每日戰報只透過這個介面和大腦互動，
所以之後把輕量模型換成真實接線或完整連接圖時，其他模組不必修改。"""

import copy

BUY, HOLD, SELL = 1, 0, -1
ACTION_NAMES = {BUY: "BUY", HOLD: "HOLD", SELL: "SELL"}


class Brain:
    kind = "base"
    learns = False

    def decide(self, pn, rng):
        """pn：當天的 PN 發放率。回傳 (動作, 記錄用資訊 dict)。"""
        raise NotImplementedError

    def reinforce(self, value, tag=None):
        """value > 0 刺激獎勵多巴胺，< 0 刺激懲罰多巴胺，0 不刺激。
        tag 是 decide() 回傳的決策標記，用來把延遲的結果對應回那一次決策。"""

    def new_episode(self):
        """換股票或換回合時清掉短期記憶（資格痕跡），不清長期權重。"""

    def state(self):
        return {}

    def load_state(self, state):
        pass

    def clone(self):
        return copy.deepcopy(self)

    def mutate(self, rng, scale):
        """淘汰賽繁殖用：回傳參數有小幅突變的子代。"""
        return self.clone()
