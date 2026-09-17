/** 学伴移动端：底部 Tab（学习/练习/讲解/我的）+ 登录态守卫（T6.1）。 */

import { NavigationContainer } from "@react-navigation/native";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import { StatusBar } from "expo-status-bar";
import { ActivityIndicator, Text, View } from "react-native";

import { GuardianGate } from "./src/components/guardian-gate";
import { AuthProvider, useAuth } from "./src/lib/auth";
import { CoachScreen } from "./src/screens/coach";
import { DiagnosisScreen, LearnHomeScreen, PlanScreen, ReviewScreen } from "./src/screens/learn";
import { LoginScreen } from "./src/screens/login";
import { PracticeScreen } from "./src/screens/practice";
import { CameraScreen, ProfileScreen, VoiceScreen } from "./src/screens/profile";
import { TutorScreen } from "./src/screens/tutor";
import type { LearnStackParamList, TabParamList } from "./src/navigation";

import "./global.css";

const Tab = createBottomTabNavigator<TabParamList>();
const LearnStack = createNativeStackNavigator<LearnStackParamList>();

function tabIcon(label: string) {
  return ({ focused }: { focused: boolean }) => (
    <Text className={focused ? "text-primary" : "text-muted"}>{label}</Text>
  );
}

function LearnNavigator() {
  return (
    <LearnStack.Navigator>
      <LearnStack.Screen name="LearnHome" component={LearnHomeScreen} options={{ headerShown: false }} />
      <LearnStack.Screen name="Diagnosis" component={DiagnosisScreen} options={{ title: "学情诊断" }} />
      <LearnStack.Screen name="Plan" component={PlanScreen} options={{ title: "学习规划" }} />
      <LearnStack.Screen name="Review" component={ReviewScreen} options={{ title: "学习复盘" }} />
      <LearnStack.Screen name="Camera" component={CameraScreen} options={{ title: "拍照搜题" }} />
      <LearnStack.Screen name="Voice" component={VoiceScreen} options={{ title: "语音助手" }} />
      <LearnStack.Screen name="Coach" component={CoachScreen} options={{ title: "陪练" }} />
    </LearnStack.Navigator>
  );
}

function MainTabs() {
  return (
    <Tab.Navigator screenOptions={{ tabBarActiveTintColor: "#1f66f5", tabBarInactiveTintColor: "#64748b" }}>
      <Tab.Screen
        name="Learn"
        component={LearnNavigator}
        options={{ headerShown: false, tabBarIcon: tabIcon("学"), tabBarLabel: "学习" }}
      />
      <Tab.Screen
        name="Practice"
        component={PracticeScreen}
        options={{ headerShown: false, tabBarIcon: tabIcon("练"), tabBarLabel: "练习" }}
      />
      <Tab.Screen
        name="Tutor"
        component={TutorScreen}
        options={{ headerShown: false, tabBarIcon: tabIcon("讲"), tabBarLabel: "讲解" }}
      />
      <Tab.Screen
        name="Profile"
        component={ProfileScreen}
        options={{ headerShown: false, tabBarIcon: tabIcon("我"), tabBarLabel: "我的" }}
      />
    </Tab.Navigator>
  );
}

function Gate() {
  const { status } = useAuth();
  if (status === "loading") {
    return (
      <View className="flex-1 items-center justify-center bg-background" accessibilityLabel="登录态检查中">
        <ActivityIndicator />
      </View>
    );
  }
  if (status === "anonymous") return <LoginScreen />;
  return (
    <NavigationContainer>
      <GuardianGate>
        <MainTabs />
      </GuardianGate>
    </NavigationContainer>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <StatusBar style="auto" />
      <Gate />
    </AuthProvider>
  );
}
