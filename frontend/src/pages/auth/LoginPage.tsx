// pages/auth/LoginPage.tsx

import React from 'react';
import { Form, Input, Button, Card, message, Divider } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate, Link } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';

interface LoginFormValues {
  email: string;
  password: string;
}

export const LoginPage: React.FC = () => {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const { login, devLogin, isLoading } = useAuthStore();

  const handleSubmit = async (values: LoginFormValues) => {
    try {
      await login(values.email, values.password);
      message.success('登录成功');
      navigate('/');
    } catch (error: any) {
      if (error.response?.status === 401) {
        message.error('邮箱或密码错误');
      } else if (error.response?.status === 404) {
        message.error('账号不存在');
      } else {
        message.error('登录失败，请稍后重试');
      }
    }
  };

  return (
    <div className="auth-page">
      <Card title="登录青云智学" className="auth-card">
        <Form form={form} onFinish={handleSubmit} layout="vertical" size="large">
          <Form.Item
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder="邮箱" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 8, message: '密码至少8个字符' },
              { max: 128, message: '密码最多128个字符' },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={isLoading}>
              登录
            </Button>
          </Form.Item>
          <div className="auth-switch">
            还没有账号？ <Link to="/register">立即注册</Link>
          </div>
          <Divider plain style={{ fontSize: 12, color: '#9CA3AF' }}>开发者模式</Divider>
          <Button
            type="dashed"
            block
            onClick={() => {
              devLogin();
              message.success('开发者登录成功');
              navigate('/');
            }}
          >
            🛠 开发者一键登录
          </Button>
        </Form>
      </Card>
    </div>
  );
};
