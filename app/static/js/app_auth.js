const { createApp, ref, reactive } = Vue;

const AuthApp = {
    // Change Vue delimiters to avoid conflict with Jinja2
    compilerOptions: {
        delimiters: ['[[', ']]']
    },
    setup() {
        const isLogin = ref(true);
        const loading = ref(false);
        const error = ref('');
        const form = reactive({
            username: '',
            email: '',
            password: '',
            role: 'student'
        });

        const submitForm = async () => {
            loading.value = true;
            error.value = '';

            const endpoint = isLogin.value ? '/auth/login' : '/auth/signup';

            try {
                const response = await axios.post(endpoint, form);
                if (response.data.success) {
                    window.location.href = response.data.redirect;
                }
            } catch (err) {
                if (err.response && err.response.data && err.response.data.message) {
                    error.value = err.response.data.message;
                } else {
                    error.value = "An error occurred. Please try again.";
                }
            } finally {
                loading.value = false;
            }
        };

        return {
            isLogin,
            loading,
            error,
            form,
            submitForm
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('auth-app')) {
        createApp(AuthApp).mount('#auth-app');
    }
});
