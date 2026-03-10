* Try to integrate agent framework, e.g., qwen agent to run our cloud agent, making each agent confiugrable in terms of available tools, etc.
* Frontend: separate dom and business logic, e.g., using vue.js, also decoupling dom from formatting logic, e.g., using css modules
* 配置wechat以及alipay登录
* 支持支付付费功能
* 单Unit的并发机制以及多节点部署机制，实现高并发处理
* 多语言支持，作为底层，自动翻译，不需要改变默认的中文
* Top-1: 资源限制模块, 单个与整体的资源限制，无论用户是免费用户还是付费用户，都需要限制资源使用，防止滥用，防止DOS攻击。