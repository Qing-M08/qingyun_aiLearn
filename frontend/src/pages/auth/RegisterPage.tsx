// pages/auth/RegisterPage.tsx

import React from 'react';
import { Form, Input, Button, Card, message } from 'antd';
import { UserOutlined, LockOutlined, MailOutlined } from '@ant-design/icons';
import { useNavigate, Link } from 'react-router-dom';
import { useAuthStore } from '../../stores/authStore';

interface RegisterFormValues {
  email: string;
  username: string;
  password: string;
  confirmPassword: string;
}

export const RegisterPage: React.FC = () => {
  const [form] = Form.useForm();
  const navigate = useNavigate();
  const { register, isLoading } = useAuthStore();

  const handleSubmit = async (values: RegisterFormValues) => {
    try {
      await register(values.email, values.username, values.password);
      message.success('注册成功，已自动登录');
      navigate('/');
    } catch (error: any) {
      if (error.response?.status === 409) {
        message.error('该邮箱已被注册');
      } else if (error.response?.data?.error?.details) {
        const details = error.response.data.error.details;
        const firstError = details[0]?.message || '注册失败';
        message.error(firstError);
      } else {
        message.error('注册失败，请稍后重试');
      }
    }
  };

  return (
    <div className="auth-page">
      <Card title="注册青云智学" className="auth-card">
        <Form form={form} onFinish={handleSubmit} layout="vertical" size="large">
          <Form.Item
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input prefix={<MailOutlined />} placeholder="邮箱" />
          </Form.Item>
          <Form.Item
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少3个字符' },
              { max: 100, message: '用户名最多100个字符' },
            ]}
          >
            <Input prefix={<UserOutlined />} placeholder="用户名" />
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
          <Form.Item
            name="confirmPassword"
            dependencies={['password']}
            rules={[
              { required: true, message: '请确认密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="确认密码" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block loading={isLoading}>
              注册
            </Button>
          </Form.Item>
          <div className="auth-switch">
            已有账号？ <Link to="/login">立即登录</Link>
          </div>
        </Form>
      </Card>
    </div>
  );
};
