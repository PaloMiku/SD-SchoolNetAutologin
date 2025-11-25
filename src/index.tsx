import {
  PanelSection,
  PanelSectionRow,
  staticClasses,
  ButtonItem,
  ToggleField,
  TextField
} from "@decky/ui";
import {
  addEventListener,
  removeEventListener,
  callable,
  definePlugin,
  toaster,
  // routerHook
} from "@decky/api"
import { useEffect } from "react";
import { useState } from "react";
import { FaShip, FaUserLock, FaPlay, FaStop, FaSave, FaSync, FaRedo } from "react-icons/fa";

// import logo from "../assets/logo.png";

type Config = {
  login_ip: string;
  use_https: boolean;
  login_path: string;
  method: string;
  params: { [key: string]: string };
  ping_target: string;
  ping_interval_sec: number;
  ping_timeout_sec: number;
  consecutive_failures_threshold: number;
  backoff_attempt_sec: number;
  success_check_string?: string;
};

type LoginResult = {
  success: boolean;
  status: number;
  body?: string;
  error?: string;
};

type PingResult = { host: string; success: boolean; rc: number; error?: string };

// const add = callable<[first: number, second: number], number>("add");
const getConfig = callable<[], Config>("get_config");
const saveConfig = callable<[config: Config], void>("save_config");
const resetConfig = callable<[], Config>("reset_config");
const doLogin = callable<[], LoginResult>("do_login");
const startPingMonitor = callable<[], void>("start_ping_monitor");
const stopPingMonitor = callable<[], void>("stop_ping_monitor");
const isMonitorRunning = callable<[], boolean>("is_monitor_running");
const testPing = callable<[], PingResult>("test_ping");

// This function calls the python function "start_timer", which takes in no arguments and returns nothing.
// It starts a (python) timer which eventually emits the event 'timer_event'
// const startTimer = callable<[], void>("start_timer");

function Content() {
  const [config, setConfig] = useState<Config | undefined>(undefined);
  const [monitorRunning, setMonitorRunning] = useState(false);
  const [pingStatus, setPingStatus] = useState<PingResult | null>(null);
  const [loginResult, setLoginResult] = useState<LoginResult | null>(null);

  useEffect(() => {
    (async () => {
      const cfg = await getConfig();
      setConfig(cfg);
      const running = await isMonitorRunning();
      setMonitorRunning(running);
    })();
    const pingListener = addEventListener<[host: string, success: boolean, consecutive: number, ts: number]>(
      "ping_status",
      (host, success, consecutive) => {
        setPingStatus({ host, success, rc: success ? 0 : 1 });
        toaster.toast({ title: "连接状态", body: `${host} ${success ? "在线" : "离线"} (${consecutive})` });
      }
    );
    const loginListener = addEventListener<[boolean, number, string, number]>("login_status", (success, status, message) => {
      setLoginResult({ success, status, body: message });
      toaster.toast({ title: "登录结果", body: `${success ? "成功" : "失败"} 状态码 ${status}` });
    });
    return () => {
      removeEventListener("ping_status", pingListener);
      removeEventListener("login_status", loginListener);
    };
  }, []);

  const onSave = async () => {
    if (config) {
      await saveConfig(config);
      toaster.toast({ title: "成功", body: "配置已保存" });
    }
  };

  const onReset = async () => {
    const defaultCfg = await resetConfig();
    setConfig(defaultCfg);
    toaster.toast({ title: "成功", body: "配置已重置为默认值" });
  };

  const onManualLogin = async () => {
    const res = await doLogin();
    setLoginResult(res);
  };

  const onStartMonitor = async () => {
    await startPingMonitor();
    setMonitorRunning(true);
  };

  const onStopMonitor = async () => {
    await stopPingMonitor();
    setMonitorRunning(false);
  };

  const onTestPing = async () => {
    const res = await testPing();
    setPingStatus(res);
  };

  const statusCardStyle = () => ({
    display: "flex" as const,
    alignItems: "center" as const,
    gap: "8px",
    padding: "4px 0"
  });

  return (
    <>
      <PanelSection title="网络状态">
        <PanelSectionRow>
          <div style={{ display: "flex", flexDirection: "column", gap: "2px", width: "100%", fontSize: "13px" }}>
            <div style={statusCardStyle()}>
              <span style={{ color: pingStatus?.success ? "#4CAF50" : "#F44336", minWidth: "16px" }}>
                {pingStatus?.success ? "✓" : "✗"}
              </span>
              <span>Ping: {pingStatus?.host ?? "未检测"} {pingStatus?.success ? "在线" : "离线"}</span>
            </div>

            <div style={statusCardStyle()}>
              <span style={{ color: loginResult?.success ? "#4CAF50" : "#F44336", minWidth: "16px" }}>
                {loginResult?.success ? "✓" : "✗"}
              </span>
              <span>登录: {loginResult?.success ? "已认证" : "失败"} ({loginResult?.status ?? "-"})</span>
            </div>

            <div style={statusCardStyle()}>
              <span style={{ color: monitorRunning ? "#2196F3" : "#9E9E9E", minWidth: "16px" }}>
                {monitorRunning ? "▶" : "■"}
              </span>
              <span>监控: {monitorRunning ? "运行中" : "已停止"}</span>
            </div>
          </div>
        </PanelSectionRow>
      </PanelSection>

      <PanelSection title="服务器配置">
        <PanelSectionRow>
          <TextField
            label="服务器 IP"
            value={config?.login_ip ?? ""}
            onChange={(e) => setConfig({ ...(config ?? {} as Config), login_ip: e.target.value })}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <ToggleField
            label="使用 HTTPS"
            checked={config?.use_https ?? false}
            onChange={(value) => setConfig({ ...(config ?? {} as Config), use_https: value })}
          />
        </PanelSectionRow>
      </PanelSection>

      <PanelSection title="登录配置">
        <PanelSectionRow>
          <TextField
            label="学号"
            value={config?.params?.DDDDD ?? ""}
            onChange={(e) => setConfig({ ...(config ?? {} as Config), params: { ...(config?.params ?? {}), DDDDD: e.target.value } })}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <TextField
            label="密码"
            value={config?.params?.upass ?? ""}
            onChange={(e) => setConfig({ ...(config ?? {} as Config), params: { ...(config?.params ?? {}), upass: e.target.value } })}
          />
        </PanelSectionRow>
      </PanelSection>

      <PanelSection title="监控设置">
        <PanelSectionRow>
          <TextField
            label="Ping 目标"
            value={config?.ping_target ?? ""}
            onChange={(e) => setConfig({ ...(config ?? {} as Config), ping_target: e.target.value })}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <TextField
            label="检测间隔(秒)"
            value={String(config?.ping_interval_sec ?? 60)}
            onChange={(e) => setConfig({ ...(config ?? {} as Config), ping_interval_sec: Number(e.target.value) })}
          />
        </PanelSectionRow>

        <PanelSectionRow>
          <TextField
            label="失败阈值(次)"
            value={String(config?.consecutive_failures_threshold ?? 3)}
            onChange={(e) => setConfig({ ...(config ?? {} as Config), consecutive_failures_threshold: Number(e.target.value) })}
          />
        </PanelSectionRow>
      </PanelSection>

      <PanelSection title="操作面板">
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onSave}>
            <FaSave /> 保存配置
          </ButtonItem>
        </PanelSectionRow>

        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onReset}>
            <FaRedo /> 重置为默认
          </ButtonItem>
        </PanelSectionRow>

        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onManualLogin}>
            <FaUserLock /> 手动登录
          </ButtonItem>
        </PanelSectionRow>

        <PanelSectionRow>
          <ButtonItem layout="below" onClick={onTestPing}>
            <FaSync /> 测试连接
          </ButtonItem>
        </PanelSectionRow>

        <PanelSectionRow>
          {!monitorRunning ? (
            <ButtonItem layout="below" onClick={onStartMonitor}>
              <FaPlay /> 启动监控
            </ButtonItem>
          ) : (
            <ButtonItem layout="below" onClick={onStopMonitor}>
              <FaStop /> 停止监控
            </ButtonItem>
          )}
        </PanelSectionRow>
      </PanelSection>
    </>
  );
};

export default definePlugin(() => {
  console.log("Template plugin initializing, this is called once on frontend startup")

  // serverApi.routerHook.addRoute("/decky-plugin-test", DeckyPluginRouterTest, {
  //   exact: true,
  // });

  // Add an event listener to the "timer_event" event from the backend
  const listener = addEventListener<[
    test1: string,
    test2: boolean,
    test3: number
  ]>("timer_event", (test1, test2, test3) => {
    console.log("Template got timer_event with:", test1, test2, test3)
    toaster.toast({
      title: "template got timer_event",
      body: `${test1}, ${test2}, ${test3}`
    });
  });

  return {
    // The name shown in various decky menus
    name: "SchNetAutologin",
    // The element displayed at the top of your plugin's menu
    titleView: <div className={staticClasses.Title}>校园网自动登录</div>,
    // The content of your plugin's menu
    content: <Content />,
    // The icon displayed in the plugin list
    icon: <FaShip />,
    // The function triggered when your plugin unloads
    onDismount() {
      console.log("Unloading")
      removeEventListener("timer_event", listener);
      // serverApi.routerHook.removeRoute("/decky-plugin-test");
    },
  };
});
