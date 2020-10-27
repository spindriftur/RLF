import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from gym import spaces
from gym_rlf.envs.fn_properties import monotonic_decreasing
from gym_rlf.envs.rlf_env import RLFEnv, action_space_normalizer, MAX_HOLDING, MIN_PRICE, MAX_PRICE
from gym_rlf.envs.Parameters import TickSize, Lambda, sigma, kappa, p_e

FUNC_PROPERTY_PENALTY = True
IS_EPISODIC = True # this must be True if FUNC_PROPERTY_PENALTY is True


class MeanReversionEnv(RLFEnv):
  def __init__(self):
    super(MeanReversionEnv, self).__init__('mean_reversion_plots/')

    self.action_space = spaces.Box(low=-1, high=1, shape=(1,))
    # Use a Box to represent the observation space with params:
    # (position), (previous price) and (current price).
    self.observation_space = spaces.Box(
      low=np.array([-MAX_HOLDING, MIN_PRICE, MIN_PRICE]),
      high=np.array([MAX_HOLDING, MAX_PRICE, MAX_PRICE]),
      shape=(3,))

  def _next_price(self, p):
    x = np.log(p / p_e)
    rn = np.random.normal(0, 1., 1)[0]
    x = x - Lambda * x + sigma * rn
    p_new = p_e * np.exp(x)
    p_new = min(p_new, MAX_PRICE)
    p_new = max(p_new, MIN_PRICE)
    return p_new

  def _get_state(self):
    return np.array([
      self._positions[self._step_counts % self._L],
      self._prices[(self._step_counts - 1) % self._L],
      self._prices[self._step_counts % self._L],
    ])
    
  def _learn_func_property(self):
    if len(self._states) <= 1: return 0
    num_prev_states = len(self._states) - 1
    penalty = 0
    for i in range(num_prev_states):
      penalty += monotonic_decreasing(self._states[i], self._states[-1], self._actions[i], self._actions[-1])

    return penalty / num_prev_states

  def reset(self):
    super(MeanReversionEnv, self).reset()

    return self._get_state()

  def step(self, action):
    ac = action[0] * action_space_normalizer

    old_pos = self._positions[self._step_counts % self._L]
    old_price = self._prices[self._step_counts % self._L]
    self._step_counts += 1
    new_pos = self._positions[self._step_counts % self._L] =\
      max(min(old_pos + ac, MAX_HOLDING), -MAX_HOLDING)
    new_price = self._prices[self._step_counts % self._L] = self._next_price(old_price)

    trade_size = abs(new_pos - old_pos)
    cost = self._costs[self._step_counts % self._L] = TickSize * (trade_size + .01 * trade_size**2)
    PnL = self._pnls[self._step_counts % self._L] = (new_price - old_price) * old_pos - cost
    reward = self._rewards[self._step_counts % self._L] = PnL - .5 * kappa * PnL**2

    fn_penalty = 0
    if FUNC_PROPERTY_PENALTY: # incorporate function property
      self._states.append(new_price)
      self._actions.append(ac)
      fn_penalty = abs(reward) * self._learn_func_property()

    done = self._step_counts == self._L if IS_EPISODIC else False
    info = {'pnl': PnL, 'cost': cost, 'reward': reward, 'penalty': fn_penalty}
    return self._get_state(), reward - fn_penalty, done, info
 
  def render(self, mode='human'):
    super(MeanReversionEnv, self).render()

    t = np.linspace(0, self._L, self._L)
    _, axs = plt.subplots(3, 1, figsize=(16, 24), constrained_layout=True)
    axs[0].plot(t, self._prices)
    axs[1].plot(t, self._positions)
    axs[2].plot(t, np.cumsum(self._pnls))
    axs[0].set_ylabel('price')
    axs[1].set_ylabel('position')
    axs[2].set_ylabel('cumulative P/L')
    plt.title('Out-of-sample simulation of RL agent')
    plt.xlabel('steps')
    plt.savefig('{}/plot_{}.png'.format(self._folder_name, self._render_counts))
    plt.close()
    
    _, axs2 = plt.subplots(4, 1, figsize=(16, 32), constrained_layout=True)
    axs2[0].plot(t, self._rewards)
    axs2[1].plot(t, np.cumsum(self._rewards))
    axs2[2].plot(t, np.cumsum(self._costs))
    axs2[3].plot(t, np.cumsum(self._pnls + self._costs))
    axs2[0].set_ylabel('reward per timestep')
    axs2[1].set_ylabel('cumulative reward')
    axs2[2].set_ylabel('cumulative costs')
    axs2[3].set_ylabel('cumulative revenues')
    plt.title('Out-of-sample reward and cost of RL agent')
    plt.xlabel('steps')
    plt.savefig('{}/reward_and_cost_{}.png'.format(self._folder_name, self._render_counts))
    plt.close()
